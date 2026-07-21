"""Canonical metadata contracts for the Enterprise Identity platform."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class IdentityStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class IdentityType(str, Enum):
    HUMAN = "HUMAN"
    SERVICE = "SERVICE"
    WORKLOAD = "WORKLOAD"


class SecretClassification(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED = "RESTRICTED"
    HIGHLY_RESTRICTED = "HIGHLY_RESTRICTED"
    TOP_SECRET = "TOP_SECRET"


class SecretStatus(str, Enum):
    CREATED = "CREATED"
    HEALTHY = "HEALTHY"
    ROTATION_DUE = "ROTATION_DUE"
    EXPIRED = "EXPIRED"
    COMPROMISED = "COMPROMISED"
    REVOKED = "REVOKED"
    DISABLED = "DISABLED"
    ARCHIVED = "ARCHIVED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class EnterpriseIdentity:
    identity_id: str
    display_name: str
    identity_type: IdentityType
    role: str
    owner: str
    environment: str
    status: IdentityStatus = IdentityStatus.ACTIVE
    created_at: str = field(default_factory=utc_now)
    last_validated: str | None = None
    permissions: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["identity_type"] = self.identity_type.value
        payload["status"] = self.status.value
        return payload


@dataclass(frozen=True)
class SecretMetadata:
    secret_uuid: str
    vcid: str
    version: int
    provider: str
    classification: SecretClassification
    rotation_status: SecretStatus
    creation_date: str
    last_validation: str | None
    expiry: str | None
    owner: str
    environment: str
    risk_score: int
    fingerprint: str
    hash: str
    secret_type: str
    broker: str | None = None
    rotation_interval_days: int = 90
    rotation_due: str | None = None
    compromised: bool = False
    revoked: bool = False
    disabled: bool = False
    archived: bool = False
    dependencies: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not 0 <= int(self.risk_score) <= 100:
            raise ValueError("SECRET_RISK_SCORE_OUT_OF_RANGE")

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["classification"] = self.classification.value
        payload["rotation_status"] = self.rotation_status.value
        payload["secret_values_returned"] = False
        payload["execution_allowed"] = False
        return payload


__all__ = [
    "EnterpriseIdentity",
    "IdentityStatus",
    "IdentityType",
    "SecretClassification",
    "SecretMetadata",
    "SecretStatus",
    "utc_now",
]
