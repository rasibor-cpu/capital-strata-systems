"""Canonical metadata-only authority for all CSS credentials and secrets."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import threading
import uuid
from typing import Any

from backend.security.credential_dependency_map import CredentialDependencyMap
from backend.security.credential_vault import CredentialVault
from backend.security.identity.identity_audit import IdentityAuditLedger
from backend.security.identity.identity_events import IdentityEventStream
from backend.security.identity.identity_models import (
    SecretClassification,
    SecretMetadata,
    SecretStatus,
    utc_now,
)
from backend.security.identity.identity_policy import IdentityPolicy, SecretAccessRequest
from backend.security.identity.secret_handle import issue_secret_handle
from backend.security.identity.runtime_secret_lease import RuntimeSecretLease
from backend.security.rotation_impact import analyze_rotation
from backend.security.vault_crypto import zeroize
from backend.security.vault_models import CredentialClassification, RotationPolicy


class DuplicateSecretError(ValueError):
    pass


class EnterpriseSecretService:
    def __init__(
        self,
        *,
        vault: CredentialVault,
        policy: IdentityPolicy | None = None,
        audit: IdentityAuditLedger | None = None,
        events: IdentityEventStream | None = None,
        dependencies: CredentialDependencyMap | None = None,
    ):
        self.vault = vault
        self.policy = policy or IdentityPolicy()
        self.audit = audit or IdentityAuditLedger()
        self.events = events or IdentityEventStream()
        self.dependencies = dependencies or CredentialDependencyMap()
        self._metadata: dict[str, SecretMetadata] = {}
        self._fingerprints: dict[str, str] = {}
        self._lock = threading.RLock()

    def register(
        self,
        material: bytes | bytearray | memoryview,
        *,
        provider: str,
        secret_type: str,
        owner: str,
        environment: str,
        operator: str,
        broker: str | None = None,
        classification: SecretClassification | None = None,
        expiry: str | None = None,
        rotation_interval_days: int = 90,
    ) -> SecretMetadata:
        resolved_classification = classification or _default_classification(secret_type, broker)
        fingerprint = self.vault.crypto.fingerprint(material)
        with self._lock:
            duplicate = self._fingerprints.get(fingerprint)
            if duplicate:
                if isinstance(material, (bytearray, memoryview)):
                    zeroize(material)
                raise DuplicateSecretError(f"DUPLICATE_SECRET_FINGERPRINT:{duplicate}")
            self._fingerprints[fingerprint] = "PENDING"
        try:
            vault_metadata = self.vault.register(
                material,
                broker=broker or provider,
                credential_type=secret_type,
                owner=owner,
                operator=operator,
                classification=_vault_classification(resolved_classification),
                rotation_policy=RotationPolicy(interval_days=rotation_interval_days),
                expiry=expiry,
            )
        except Exception:
            with self._lock:
                if self._fingerprints.get(fingerprint) == "PENDING":
                    self._fingerprints.pop(fingerprint, None)
            raise
        secret_uuid = f"SUUID-{uuid.uuid4()}"
        creation = utc_now()
        metadata = SecretMetadata(
            secret_uuid=secret_uuid,
            vcid=vault_metadata.vcid,
            version=vault_metadata.version,
            provider=str(provider).upper(),
            classification=resolved_classification,
            rotation_status=SecretStatus.CREATED,
            creation_date=creation,
            last_validation=None,
            expiry=expiry,
            owner=str(owner),
            environment=str(environment).upper(),
            risk_score=_risk_score(resolved_classification, SecretStatus.CREATED, expiry),
            fingerprint=fingerprint,
            hash=hashlib.sha256(f"{secret_uuid}|{fingerprint}".encode("utf-8")).hexdigest(),
            secret_type=str(secret_type).upper(),
            broker=str(broker).upper() if broker else None,
            rotation_interval_days=max(1, int(rotation_interval_days)),
            rotation_due=(
                datetime.now(timezone.utc) + timedelta(days=max(1, int(rotation_interval_days)))
            ).isoformat(),
        )
        with self._lock:
            self._metadata[secret_uuid] = metadata
            self._fingerprints[fingerprint] = secret_uuid
        self.events.publish(
            event_type="SECRET_REGISTERED",
            identity_id=operator,
            resource_id=secret_uuid,
            result="SUCCESS",
        )
        return metadata

    def retrieve(self, secret_uuid: str, *, request: SecretAccessRequest) -> dict[str, Any]:
        handle = self.issue_handle(secret_uuid, request=request)
        metadata = self._get(secret_uuid)
        return {
            "handle": handle.as_dict(),
            "metadata": metadata.as_dict(),
            "fingerprint": metadata.fingerprint,
            "hash": metadata.hash,
            "classification": metadata.classification.value,
            "plaintext_returned": False,
            "execution_allowed": False,
        }

    def issue_handle(self, secret_uuid: str, *, request: SecretAccessRequest):
        """Return an opaque SecretHandle after policy and audit checks."""
        metadata = self._get(secret_uuid)
        decision = self.policy.evaluate(request, metadata)
        result = "SUCCESS" if decision.allowed else "DENIED"
        self.audit.append(
            who=request.identity.identity_id,
            role=request.identity.role,
            resource_id=secret_uuid,
            why=request.purpose,
            component=request.component,
            duration_seconds=request.duration_seconds,
            reason=decision.reason,
            result=result,
        )
        self.events.publish(
            event_type="SECRET_HANDLE_REQUESTED",
            identity_id=request.identity.identity_id,
            resource_id=secret_uuid,
            result=result,
        )
        if not decision.allowed:
            raise PermissionError(decision.reason)
        return issue_secret_handle(
            metadata,
            identity_id=request.identity.identity_id,
            purpose=request.purpose,
        )

    def _get(self, secret_uuid: str) -> SecretMetadata:
        with self._lock:
            metadata = self._metadata.get(str(secret_uuid))
        if metadata is None:
            raise KeyError("SECRET_NOT_FOUND")
        return metadata

    def metadata(self, secret_uuid: str) -> dict[str, Any]:
        """Public metadata-only lookup; never returns encrypted or plaintext material."""
        return self._get(secret_uuid).as_dict()

    def find_by_fingerprint(self, fingerprint: str) -> SecretMetadata | None:
        with self._lock:
            secret_uuid = self._fingerprints.get(str(fingerprint))
            if not secret_uuid or secret_uuid == "PENDING":
                return None
            return self._metadata.get(secret_uuid)

    def _inventory(self) -> list[dict[str, Any]]:
        with self._lock:
            return [metadata.as_dict() for metadata in self._metadata.values()]

    def inventory(self, *, request: SecretAccessRequest) -> list[dict[str, Any]]:
        decision = self.policy.evaluate_identity_request(request)
        self.audit.append(
            who=request.identity.identity_id,
            role=request.identity.role,
            resource_id="SECRET_INVENTORY",
            why=request.purpose,
            component=request.component,
            duration_seconds=request.duration_seconds,
            reason=decision.reason,
            result="SUCCESS" if decision.allowed else "DENIED",
        )
        if not decision.allowed:
            raise PermissionError(decision.reason)
        return self._inventory()

    def register_dependency(
        self,
        secret_uuid: str,
        consumer: str,
        *,
        safe_to_pause: bool = True,
        rollback_supported: bool = True,
    ) -> None:
        metadata = self._get(secret_uuid)
        self.dependencies.register(
            metadata.vcid,
            consumer,
            safe_to_pause=safe_to_pause,
            rollback_supported=rollback_supported,
        )
        with self._lock:
            self._metadata[secret_uuid] = replace(
                metadata,
                dependencies=tuple(sorted({*metadata.dependencies, str(consumer)})),
            )

    def authorize_runtime_consumer(
        self,
        secret_uuid: str,
        *,
        consumer: str,
        operator: str,
    ) -> None:
        """Bind an enterprise secret to one approved runtime consumer."""
        metadata = self._get(secret_uuid)
        self.vault.authorize_consumer(metadata.vcid, consumer=consumer, operator=operator)
        self.register_dependency(secret_uuid, consumer)

    def issue_runtime_lease(
        self,
        secret_uuid: str,
        *,
        consumer: str,
        capability: str,
        operator: str,
        duration_seconds: int = 60,
        correlation_id: str | None = None,
    ) -> RuntimeSecretLease:
        """Issue an opaque, short-lived lease without returning secret material."""
        metadata = self._get(secret_uuid)
        handle = self.vault.issue_runtime_handle(
            metadata.vcid,
            consumer=consumer,
            operator=operator,
        )
        self.events.publish(
            event_type="RUNTIME_SECRET_LEASE_ISSUED",
            identity_id=operator,
            resource_id=secret_uuid,
            result="SUCCESS",
        )
        return RuntimeSecretLease(
            vault=self.vault,
            vault_handle=handle,
            secret_uuid=secret_uuid,
            consumer=consumer,
            broker=metadata.broker or metadata.provider,
            capability=capability,
            duration_seconds=duration_seconds,
            correlation_id=correlation_id,
        )

    def rotation_status(self, *, now: datetime | None = None) -> dict[str, Any]:
        current = now or datetime.now(timezone.utc)
        rows = []
        for metadata in list(self._metadata.values()):
            expiry = _parse_time(metadata.expiry)
            due = _parse_time(metadata.rotation_due)
            status = metadata.rotation_status
            if expiry and current >= expiry:
                status = SecretStatus.EXPIRED
            elif due and current >= due and status is SecretStatus.CREATED:
                status = SecretStatus.ROTATION_DUE
            rows.append({**metadata.as_dict(), "effective_status": status.value})
        return {
            "secrets": rows,
            "reminders": [
                row for row in rows
                if row["effective_status"] in {"ROTATION_DUE", "EXPIRED"}
            ],
            "automatic_rotation": False,
            "execution_allowed": False,
        }

    def rotation_impact(self, secret_uuid: str) -> dict[str, Any]:
        metadata = self._get(secret_uuid)
        impact = analyze_rotation(metadata.vcid, self.dependencies)
        return {**impact.__dict__, "secret_uuid": secret_uuid, "automatic_rotation": False}

    def set_status(
        self,
        secret_uuid: str,
        status: SecretStatus,
        *,
        operator: str,
        operator_role: str,
        reason: str,
    ) -> SecretMetadata:
        metadata = self._get(secret_uuid)
        if str(operator_role).upper() not in self.policy.allowed_roles:
            self.audit.append(
                who=operator,
                role=operator_role,
                resource_id=secret_uuid,
                why=reason,
                component="EnterpriseSecretService",
                duration_seconds=0,
                reason="ROLE_NOT_AUTHORIZED",
                result="DENIED",
            )
            raise PermissionError("ROLE_NOT_AUTHORIZED")
        updated = replace(
            metadata,
            rotation_status=status,
            compromised=status is SecretStatus.COMPROMISED,
            revoked=status is SecretStatus.REVOKED,
            disabled=status is SecretStatus.DISABLED,
            archived=status is SecretStatus.ARCHIVED,
            risk_score=_risk_score(metadata.classification, status, metadata.expiry),
        )
        with self._lock:
            self._metadata[secret_uuid] = updated
        self.audit.append(
            who=operator,
            role=operator_role,
            resource_id=secret_uuid,
            why=reason,
            component="EnterpriseSecretService",
            duration_seconds=0,
            reason=status.value,
            result="SUCCESS",
        )
        return updated

    def risk_summary(self) -> dict[str, Any]:
        rows = sorted(self._inventory(), key=lambda row: int(row["risk_score"]), reverse=True)
        return {
            "secret_count": len(rows),
            "high_risk_count": sum(int(row["risk_score"]) >= 70 for row in rows),
            "maximum_risk_score": max((int(row["risk_score"]) for row in rows), default=0),
            "rows": rows,
            "execution_allowed": False,
        }


def _default_classification(secret_type: str, broker: str | None) -> SecretClassification:
    normalized = str(secret_type).upper()
    if "REFRESH_TOKEN" in normalized:
        return SecretClassification.TOP_SECRET
    if broker or any(
        token in normalized
        for token in ("API_KEY", "PRIVATE_KEY", "BROKER", "PASSWORD", "ACCESS_TOKEN", "OAUTH")
    ):
        return SecretClassification.HIGHLY_RESTRICTED
    return SecretClassification.RESTRICTED


def _vault_classification(value: SecretClassification) -> CredentialClassification:
    if value is SecretClassification.PUBLIC or value is SecretClassification.INTERNAL:
        return CredentialClassification.INTERNAL
    if value is SecretClassification.CONFIDENTIAL:
        return CredentialClassification.CONFIDENTIAL
    return CredentialClassification.RESTRICTED


def _risk_score(
    classification: SecretClassification,
    status: SecretStatus,
    expiry: str | None,
) -> int:
    base = {
        SecretClassification.PUBLIC: 5,
        SecretClassification.INTERNAL: 15,
        SecretClassification.CONFIDENTIAL: 30,
        SecretClassification.RESTRICTED: 45,
        SecretClassification.HIGHLY_RESTRICTED: 65,
        SecretClassification.TOP_SECRET: 80,
    }[classification]
    if status in {SecretStatus.COMPROMISED, SecretStatus.REVOKED, SecretStatus.FAILED}:
        base += 20
    if expiry and (_parse_time(expiry) or datetime.max.replace(tzinfo=timezone.utc)) <= datetime.now(timezone.utc):
        base += 10
    return min(100, base)


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


__all__ = ["DuplicateSecretError", "EnterpriseSecretService"]
