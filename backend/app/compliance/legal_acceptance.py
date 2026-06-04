from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class AcceptanceValidationStatus(str, Enum):
    ALLOW = 'ALLOW'
    BLOCK = 'BLOCK'


class AcceptanceBlockReason(str, Enum):
    NONE = 'NONE'
    MISSING_ACCEPTANCE = 'MISSING_ACCEPTANCE'
    INVALID_ACCEPTANCE = 'INVALID_ACCEPTANCE'
    OUTDATED_ACCEPTANCE = 'OUTDATED_ACCEPTANCE'


@dataclass(frozen=True)
class LegalAcceptanceRecord:
    user_id: str
    acceptance_type: str
    acceptance_version: str
    accepted: bool
    accepted_at: datetime
    audit_reference: str


@dataclass(frozen=True)
class AcceptanceValidationResult:
    status: AcceptanceValidationStatus
    reason: AcceptanceBlockReason

    @property
    def allowed(self) -> bool:
        return self.status == AcceptanceValidationStatus.ALLOW
