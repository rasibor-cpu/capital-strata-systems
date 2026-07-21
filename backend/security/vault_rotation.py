"""Credential rotation metadata and encrypted replacement workflow."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.security.credential_vault import CredentialVault, _payload, _record
from backend.security.vault_crypto import zeroize
from backend.security.vault_models import CredentialHealth, CredentialMetadata, utc_now


@dataclass(frozen=True)
class RotationResult:
    vcid: str
    status: str
    previous_version: int
    new_version: int
    rollback_available: bool
    execution_allowed: bool = False


class VaultRotationManager:
    def __init__(self, vault: CredentialVault):
        self.vault = vault

    def due(self, metadata: CredentialMetadata, *, now: datetime | None = None) -> bool:
        current = now or datetime.now(timezone.utc)
        updated = datetime.fromisoformat(metadata.updated.replace("Z", "+00:00"))
        return current >= updated + timedelta(days=metadata.rotation_policy.interval_days)

    def rotate(
        self,
        vcid: str,
        replacement: bytes | bytearray | memoryview,
        *,
        operator: str,
    ) -> RotationResult:
        if not replacement:
            raise ValueError("ROTATION_REPLACEMENT_REQUIRED")
        current = self.vault.storage.get(vcid)
        if current is None:
            raise KeyError("CREDENTIAL_NOT_FOUND")
        now = utc_now()
        metadata = replace(
            current.metadata,
            updated=now,
            health=CredentialHealth.ROTATING,
            fingerprint=self.vault.crypto.fingerprint(replacement),
            version=current.metadata.version + 1,
            rotation_due=None,
        )
        encrypted = self.vault.crypto.encrypt(replacement, aad=self.vault._aad(metadata))
        if isinstance(replacement, (bytearray, memoryview)):
            zeroize(replacement)
        self.vault.storage.put(_record(replace(metadata, health=CredentialHealth.HEALTHY), encrypted))
        self.vault.audit.record(
            operator=operator,
            service="vault_rotation",
            broker=metadata.broker,
            credential_id=vcid,
            action="ROTATE",
            success=True,
            reason_code="ROTATION_COMPLETE",
        )
        return RotationResult(
            vcid=vcid,
            status="HEALTHY",
            previous_version=current.metadata.version,
            new_version=metadata.version,
            rollback_available=current.metadata.rotation_policy.rollback_required,
        )


__all__ = ["RotationResult", "VaultRotationManager"]
