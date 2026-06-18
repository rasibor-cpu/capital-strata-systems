from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class AcceptanceValidationStatus(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"


class AcceptanceBlockReason(str, Enum):
    NONE = "NONE"
    MISSING_ACCEPTANCE = "MISSING_ACCEPTANCE"
    INVALID_ACCEPTANCE = "INVALID_ACCEPTANCE"
    OUTDATED_ACCEPTANCE = "OUTDATED_ACCEPTANCE"


@dataclass(frozen=True)
class LegalAcceptanceRecord:
    user_id: str
    acceptance_type: str
    acceptance_version: str
    accepted: bool
    accepted_at: datetime
    audit_reference: str

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "LegalAcceptanceRecord":
        accepted_at = payload["accepted_at"]
        if isinstance(accepted_at, str):
            accepted_at = datetime.fromisoformat(accepted_at)

        return cls(
            user_id=str(payload["user_id"]),
            acceptance_type=str(payload["acceptance_type"]),
            acceptance_version=str(payload["acceptance_version"]),
            accepted=bool(payload["accepted"]),
            accepted_at=accepted_at,
            audit_reference=str(payload["audit_reference"]),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "acceptance_type": self.acceptance_type,
            "acceptance_version": self.acceptance_version,
            "accepted": self.accepted,
            "accepted_at": self.accepted_at.astimezone(UTC).isoformat(),
            "audit_reference": self.audit_reference,
        }


@dataclass(frozen=True)
class AcceptanceValidationResult:
    status: AcceptanceValidationStatus
    acceptance_type: str = ""
    required_version: str | None = None
    record: LegalAcceptanceRecord | None = None
    block_reason: AcceptanceBlockReason | None = None
    message: str = ""

    @property
    def reason(self) -> AcceptanceBlockReason | None:
        return self.block_reason

    @property
    def allowed(self) -> bool:
        return self.status == AcceptanceValidationStatus.ALLOW

    @property
    def blocked(self) -> bool:
        return self.status == AcceptanceValidationStatus.BLOCK


def validate_acceptance_record_shape(record: LegalAcceptanceRecord) -> bool:
    if not record.user_id:
        return False

    if not record.acceptance_type:
        return False

    if not record.acceptance_version:
        return False

    if not record.audit_reference:
        return False

    if not record.accepted:
        return False

    return True