"""Capability-bound ephemeral runtime access to an enterprise-vault secret."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import threading
import uuid
from typing import Any, Iterator

from backend.security.credential_vault import CredentialVault
from backend.security.vault_handles import VaultHandle


@dataclass(frozen=True)
class RuntimeSecretLeaseMetadata:
    lease_id: str
    secret_uuid: str
    vcid: str
    consumer: str
    broker: str
    capability: str
    issued_at: str
    expires_at: str
    correlation_id: str


class RuntimeSecretLease:
    """Opaque lease; plaintext exists only inside ``open`` and is zeroized by the vault."""

    def __init__(
        self,
        *,
        vault: CredentialVault,
        vault_handle: VaultHandle,
        secret_uuid: str,
        consumer: str,
        broker: str,
        capability: str,
        duration_seconds: int,
        correlation_id: str | None = None,
    ):
        now = datetime.now(timezone.utc)
        self._vault = vault
        self._handle = vault_handle
        self._revoked = False
        self._open_count = 0
        self._lock = threading.RLock()
        self.metadata = RuntimeSecretLeaseMetadata(
            lease_id=f"RSL-{uuid.uuid4()}",
            secret_uuid=str(secret_uuid),
            vcid=vault_handle.vcid,
            consumer=str(consumer),
            broker=str(broker).upper(),
            capability=str(capability).upper(),
            issued_at=now.isoformat(),
            expires_at=(now + timedelta(seconds=max(1, min(int(duration_seconds), 300)))).isoformat(),
            correlation_id=str(correlation_id or uuid.uuid4()),
        )

    @contextmanager
    def open(self, *, consumer: str, capability: str) -> Iterator[memoryview]:
        with self._lock:
            if self._revoked:
                raise PermissionError("RUNTIME_SECRET_LEASE_REVOKED")
            if datetime.now(timezone.utc) >= datetime.fromisoformat(self.metadata.expires_at):
                raise PermissionError("RUNTIME_SECRET_LEASE_EXPIRED")
            if str(consumer) != self.metadata.consumer:
                raise PermissionError("RUNTIME_SECRET_LEASE_CONSUMER_MISMATCH")
            if str(capability).upper() != self.metadata.capability:
                raise PermissionError("RUNTIME_SECRET_LEASE_CAPABILITY_MISMATCH")
            self._open_count += 1
        with self._vault.open_runtime_lease(
            self._handle,
            consumer=self.metadata.consumer,
            correlation_id=self.metadata.correlation_id,
        ) as material:
            yield material

    def revoke(self) -> None:
        with self._lock:
            self._revoked = True

    def health(self) -> dict[str, Any]:
        with self._lock:
            expired = datetime.now(timezone.utc) >= datetime.fromisoformat(self.metadata.expires_at)
            status = "REVOKED" if self._revoked else ("EXPIRED" if expired else "HEALTHY")
            return {
                **asdict(self.metadata),
                "status": status,
                "open_count": self._open_count,
                "plaintext_returned": False,
                "serializable_secret_material": False,
                "execution_allowed": False,
            }

    def __repr__(self) -> str:
        return (
            f"RuntimeSecretLease(lease_id={self.metadata.lease_id!r}, "
            f"consumer={self.metadata.consumer!r}, capability={self.metadata.capability!r}, "
            "secret_material_redacted=True)"
        )


__all__ = ["RuntimeSecretLease", "RuntimeSecretLeaseMetadata"]
