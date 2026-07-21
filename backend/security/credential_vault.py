"""Canonical encrypted credential vault for ESMS-001."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import threading
import uuid
from typing import Any, Iterator, Protocol

from backend.security.vault_audit import VaultAuditLog
from backend.security.vault_crypto import EncryptedPayload, VaultCrypto, VaultIntegrityError, zeroize
from backend.security.vault_handles import VCIDGenerator, VaultHandle, issue_handle
from backend.security.vault_models import (
    CredentialClassification,
    CredentialHealth,
    CredentialMetadata,
    EncryptedCredentialRecord,
    RotationPolicy,
    ValidationRecord,
    VaultHealth,
    metadata_from_dict,
    utc_now,
)
from backend.security.vault_policy import VaultPolicy


class EncryptedStorage(Protocol):
    def put(self, record: EncryptedCredentialRecord) -> None: ...
    def get(self, vcid: str) -> EncryptedCredentialRecord | None: ...
    def list(self) -> list[EncryptedCredentialRecord]: ...
    def delete(self, vcid: str) -> bool: ...


class InMemoryEncryptedStorage:
    def __init__(self):
        self._records: dict[str, EncryptedCredentialRecord] = {}
        self._lock = threading.RLock()

    def put(self, record: EncryptedCredentialRecord) -> None:
        with self._lock:
            self._records[record.metadata.vcid] = record

    def get(self, vcid: str) -> EncryptedCredentialRecord | None:
        with self._lock:
            return self._records.get(str(vcid))

    def list(self) -> list[EncryptedCredentialRecord]:
        with self._lock:
            return list(self._records.values())

    def delete(self, vcid: str) -> bool:
        with self._lock:
            return self._records.pop(str(vcid), None) is not None


class FileEncryptedStorage:
    """One encrypted JSON record per VCID; key material is never stored here."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, vcid: str) -> Path:
        if not str(vcid).startswith("VCID-"):
            raise ValueError("INVALID_VCID")
        return self.root / f"{vcid}.vault.json"

    def put(self, record: EncryptedCredentialRecord) -> None:
        target = self._path(record.metadata.vcid)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(record.as_dict(), sort_keys=True), encoding="utf-8")
        os.replace(temporary, target)

    def get(self, vcid: str) -> EncryptedCredentialRecord | None:
        path = self._path(vcid)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return _record_from_dict(payload)
        except Exception as exc:
            raise VaultIntegrityError("VAULT_RECORD_CORRUPTED") from exc

    def list(self) -> list[EncryptedCredentialRecord]:
        records = []
        for path in sorted(self.root.glob("VCID-*.vault.json")):
            try:
                records.append(_record_from_dict(json.loads(path.read_text(encoding="utf-8"))))
            except Exception as exc:
                raise VaultIntegrityError("VAULT_STORAGE_CORRUPTION_DETECTED") from exc
        return records

    def delete(self, vcid: str) -> bool:
        path = self._path(vcid)
        if not path.exists():
            return False
        try:
            size = path.stat().st_size
            with path.open("r+b", buffering=0) as stream:
                stream.write(os.urandom(size))
                stream.flush()
                os.fsync(stream.fileno())
        finally:
            path.unlink(missing_ok=True)
        return True


class CredentialVault:
    def __init__(
        self,
        *,
        crypto: VaultCrypto,
        storage: EncryptedStorage | None = None,
        audit: VaultAuditLog | None = None,
        policy: VaultPolicy | None = None,
        vcids: VCIDGenerator | None = None,
    ):
        self.crypto = crypto
        self.storage = storage or InMemoryEncryptedStorage()
        self.audit = audit or VaultAuditLog()
        self.policy = policy or VaultPolicy()
        self.vcids = vcids or VCIDGenerator()

    def register(
        self,
        secret: bytes | bytearray | memoryview,
        *,
        broker: str,
        credential_type: str,
        owner: str,
        operator: str,
        classification: CredentialClassification = CredentialClassification.RESTRICTED,
        rotation_policy: RotationPolicy | None = None,
        expiry: str | None = None,
        correlation_id: str | None = None,
    ) -> CredentialMetadata:
        if not isinstance(secret, (bytes, bytearray, memoryview)) or len(secret) == 0:
            raise ValueError("NONEMPTY_BINARY_SECRET_REQUIRED")
        vcid = self.vcids.issue(broker, credential_type)
        now = utc_now()
        metadata = CredentialMetadata(
            vcid=vcid,
            broker=str(broker).upper(),
            credential_type=str(credential_type).upper(),
            classification=classification,
            created=now,
            updated=now,
            rotation_policy=rotation_policy or RotationPolicy(),
            expiry=expiry,
            owner=str(owner),
            health=CredentialHealth.CREATED,
            audit_id=str(uuid.uuid4()),
            fingerprint=self.crypto.fingerprint(secret),
        )
        payload = self.crypto.encrypt(secret, aad=self._aad(metadata))
        self.storage.put(_record(metadata, payload))
        if isinstance(secret, (bytearray, memoryview)):
            zeroize(secret)
        self.audit.record(
            operator=operator,
            service="credential_vault",
            broker=metadata.broker,
            credential_id=vcid,
            action="REGISTER",
            success=True,
            reason_code="ENCRYPTED_AND_REGISTERED",
            correlation_id=correlation_id,
        )
        return metadata

    def metadata(self, vcid: str) -> CredentialMetadata:
        record = self.storage.get(vcid)
        if record is None:
            raise KeyError("CREDENTIAL_NOT_FOUND")
        return record.metadata

    def inventory(self) -> list[dict[str, Any]]:
        return [record.metadata.as_dict() for record in self.storage.list()]

    def authorize_consumer(self, vcid: str, *, consumer: str, operator: str) -> None:
        metadata = self.metadata(vcid)
        self.policy.authorize_consumer(vcid, consumer)
        self.audit.record(
            operator=operator,
            service="vault_policy",
            broker=metadata.broker,
            credential_id=vcid,
            action="AUTHORIZE_CONSUMER",
            success=True,
            reason_code="LEAST_PRIVILEGE_BINDING_ADDED",
        )

    def issue_runtime_handle(self, vcid: str, *, consumer: str, operator: str) -> VaultHandle:
        metadata = self.metadata(vcid)
        if str(consumer) not in self.policy.consumer_inventory(vcid):
            self.audit.record(
                operator=operator,
                service=consumer,
                broker=metadata.broker,
                credential_id=vcid,
                action="ISSUE_HANDLE",
                success=False,
                reason_code="CONSUMER_NOT_AUTHORIZED",
            )
            raise PermissionError("CONSUMER_NOT_AUTHORIZED")
        handle = issue_handle(
            vcid=vcid,
            fingerprint=metadata.fingerprint,
            capability="RUNTIME_USE",
            consumer=consumer,
        )
        self.audit.record(
            operator=operator,
            service=consumer,
            broker=metadata.broker,
            credential_id=vcid,
            action="ISSUE_HANDLE",
            success=True,
            reason_code="METADATA_ONLY_HANDLE",
        )
        return handle

    @contextmanager
    def open_runtime_lease(
        self,
        handle: VaultHandle,
        *,
        consumer: str,
        correlation_id: str | None = None,
    ) -> Iterator[memoryview]:
        decision = self.policy.runtime_lease(handle, consumer=consumer)
        if not decision.allowed:
            self.audit.record(
                operator=consumer,
                service=consumer,
                broker="NONE",
                credential_id=handle.vcid,
                action="OPEN_RUNTIME_LEASE",
                success=False,
                reason_code=decision.reason_code,
                correlation_id=correlation_id,
            )
            raise PermissionError(decision.reason_code)
        record = self.storage.get(handle.vcid)
        if record is None or record.metadata.fingerprint != handle.fingerprint:
            raise PermissionError("HANDLE_RECORD_MISMATCH")
        plaintext = self.crypto.decrypt(_payload(record), aad=self._aad(record.metadata))
        self.audit.record(
            operator=consumer,
            service=consumer,
            broker=record.metadata.broker,
            credential_id=handle.vcid,
            action="OPEN_RUNTIME_LEASE",
            success=True,
            reason_code="EPHEMERAL_ACCESS_GRANTED",
            correlation_id=correlation_id,
        )
        try:
            yield memoryview(plaintext)
        finally:
            zeroize(plaintext)

    def validate_integrity(self, vcid: str, *, operator: str = "SYSTEM") -> bool:
        record = self.storage.get(vcid)
        if record is None:
            return False
        plaintext: bytearray | None = None
        try:
            plaintext = self.crypto.decrypt(_payload(record), aad=self._aad(record.metadata))
            success = self.crypto.fingerprint(plaintext) == record.metadata.fingerprint
        except VaultIntegrityError:
            success = False
        finally:
            if plaintext is not None:
                zeroize(plaintext)
        self.audit.record(
            operator=operator,
            service="credential_vault",
            broker=record.metadata.broker,
            credential_id=vcid,
            action="VERIFY_INTEGRITY",
            success=success,
            reason_code="INTEGRITY_VERIFIED" if success else "CORRUPTION_DETECTED",
        )
        return success

    def record_validation(
        self,
        vcid: str,
        *,
        validator: str,
        success: bool,
        reason_code: str,
        correlation_id: str | None = None,
    ) -> CredentialMetadata:
        record = self.storage.get(vcid)
        if record is None:
            raise KeyError("CREDENTIAL_NOT_FOUND")
        event = ValidationRecord(
            timestamp=utc_now(),
            validator=validator,
            success=bool(success),
            reason_code=str(reason_code).upper(),
            correlation_id=str(correlation_id or uuid.uuid4()),
        )
        metadata = replace(
            record.metadata,
            updated=event.timestamp,
            last_validated=event.timestamp,
            health=CredentialHealth.HEALTHY if success else CredentialHealth.DEGRADED,
            validation_history=(*record.metadata.validation_history, event)[-25:],
        )
        self.storage.put(replace(record, metadata=metadata))
        self.audit.record(
            operator=validator,
            service="credential_validation",
            broker=metadata.broker,
            credential_id=vcid,
            action="VALIDATE",
            success=success,
            reason_code=reason_code,
            correlation_id=event.correlation_id,
        )
        return metadata

    def delete(self, vcid: str, *, operator: str, reason: str) -> bool:
        metadata = self.metadata(vcid)
        deleted = self.storage.delete(vcid)
        self.audit.record(
            operator=operator,
            service="credential_vault",
            broker=metadata.broker,
            credential_id=vcid,
            action="SECURE_DELETE",
            success=deleted,
            reason_code=str(reason).upper(),
        )
        return deleted

    def health(self) -> VaultHealth:
        try:
            records = self.storage.list()
        except (VaultIntegrityError, ValueError, OSError):
            return VaultHealth(
                status="FAILED",
                record_count=0,
                integrity_verified=False,
                corruption_count=1,
            )
        corrupt = sum(not self.validate_integrity(row.metadata.vcid) for row in records)
        return VaultHealth(
            status="HEALTHY" if corrupt == 0 else "FAILED",
            record_count=len(records),
            integrity_verified=corrupt == 0,
            corruption_count=corrupt,
        )

    @staticmethod
    def _aad(metadata: CredentialMetadata) -> bytes:
        return VaultCrypto.canonical_aad(metadata.as_dict())


def _record(metadata: CredentialMetadata, payload: EncryptedPayload) -> EncryptedCredentialRecord:
    return EncryptedCredentialRecord(metadata=metadata, **payload.__dict__)


def _payload(record: EncryptedCredentialRecord) -> EncryptedPayload:
    return EncryptedPayload(
        nonce_b64=record.nonce_b64,
        ciphertext_b64=record.ciphertext_b64,
        aad_sha256=record.aad_sha256,
        record_sha256=record.record_sha256,
    )


def _record_from_dict(value: dict[str, Any]) -> EncryptedCredentialRecord:
    return EncryptedCredentialRecord(
        metadata=metadata_from_dict(value["metadata"]),
        nonce_b64=str(value["nonce_b64"]),
        ciphertext_b64=str(value["ciphertext_b64"]),
        aad_sha256=str(value["aad_sha256"]),
        record_sha256=str(value["record_sha256"]),
    )


__all__ = [
    "CredentialVault",
    "EncryptedStorage",
    "FileEncryptedStorage",
    "InMemoryEncryptedStorage",
]
