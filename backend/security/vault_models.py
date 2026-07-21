"""Canonical metadata-only models for Enterprise Secret Management."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CredentialHealth(str, Enum):
    CREATED = "CREATED"
    VALIDATED = "VALIDATED"
    ROTATING = "ROTATING"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"


class CredentialClassification(str, Enum):
    RESTRICTED = "RESTRICTED"
    CONFIDENTIAL = "CONFIDENTIAL"
    INTERNAL = "INTERNAL"


@dataclass(frozen=True)
class RotationPolicy:
    interval_days: int = 90
    warning_days: int = 14
    automatic: bool = False
    rollback_required: bool = True

    def __post_init__(self) -> None:
        if self.interval_days < 1 or self.warning_days < 0:
            raise ValueError("INVALID_ROTATION_POLICY")


@dataclass(frozen=True)
class ValidationRecord:
    timestamp: str
    validator: str
    success: bool
    reason_code: str
    correlation_id: str


@dataclass(frozen=True)
class CredentialMetadata:
    vcid: str
    broker: str
    credential_type: str
    classification: CredentialClassification
    created: str
    updated: str
    rotation_policy: RotationPolicy
    expiry: str | None
    owner: str
    health: CredentialHealth
    audit_id: str
    fingerprint: str
    last_validated: str | None = None
    last_refresh: str | None = None
    rotation_due: str | None = None
    validation_history: tuple[ValidationRecord, ...] = ()
    encryption_algorithm: str = "AES-256-GCM"
    least_privilege: bool = True
    version: int = 1

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["classification"] = self.classification.value
        payload["health"] = self.health.value
        return payload


@dataclass(frozen=True)
class EncryptedCredentialRecord:
    metadata: CredentialMetadata
    nonce_b64: str
    ciphertext_b64: str
    aad_sha256: str
    record_sha256: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata.as_dict(),
            "nonce_b64": self.nonce_b64,
            "ciphertext_b64": self.ciphertext_b64,
            "aad_sha256": self.aad_sha256,
            "record_sha256": self.record_sha256,
        }


@dataclass(frozen=True)
class BackupMetadata:
    backup_id: str
    created: str
    record_count: int
    manifest_sha256: str
    encryption_status: str = "ENCRYPTED_RECORDS_ONLY"
    contains_plaintext: bool = False


@dataclass(frozen=True)
class VaultHealth:
    status: str
    record_count: int
    integrity_verified: bool
    corruption_count: int
    encryption_algorithm: str = "AES-256-GCM"
    advisory_only: bool = True
    execution_allowed: bool = False


def metadata_from_dict(value: Mapping[str, Any]) -> CredentialMetadata:
    policy = value.get("rotation_policy") or {}
    history = tuple(
        ValidationRecord(**dict(row))
        for row in value.get("validation_history", ())
        if isinstance(row, Mapping)
    )
    return CredentialMetadata(
        vcid=str(value["vcid"]),
        broker=str(value["broker"]),
        credential_type=str(value["credential_type"]),
        classification=CredentialClassification(str(value["classification"])),
        created=str(value["created"]),
        updated=str(value["updated"]),
        rotation_policy=RotationPolicy(**dict(policy)),
        expiry=str(value["expiry"]) if value.get("expiry") else None,
        owner=str(value["owner"]),
        health=CredentialHealth(str(value["health"])),
        audit_id=str(value["audit_id"]),
        fingerprint=str(value["fingerprint"]),
        last_validated=str(value["last_validated"]) if value.get("last_validated") else None,
        last_refresh=str(value["last_refresh"]) if value.get("last_refresh") else None,
        rotation_due=str(value["rotation_due"]) if value.get("rotation_due") else None,
        validation_history=history,
        encryption_algorithm=str(value.get("encryption_algorithm") or "AES-256-GCM"),
        least_privilege=bool(value.get("least_privilege", True)),
        version=int(value.get("version", 1)),
    )


__all__ = [
    "BackupMetadata",
    "CredentialClassification",
    "CredentialHealth",
    "CredentialMetadata",
    "EncryptedCredentialRecord",
    "RotationPolicy",
    "ValidationRecord",
    "VaultHealth",
    "metadata_from_dict",
    "utc_now",
]
