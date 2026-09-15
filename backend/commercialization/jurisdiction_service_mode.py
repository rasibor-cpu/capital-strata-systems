from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class ServiceMode(str, Enum):
    DISCOVER = "DISCOVER"
    CONFIRM = "CONFIRM"
    AUTO = "AUTO"


class JurisdictionModeApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    RESTRICTED = "RESTRICTED"
    PROHIBITED = "PROHIBITED"


@dataclass(frozen=True, slots=True)
class JurisdictionServiceModeApproval:
    approval_id: str
    jurisdiction_code: str
    service_mode: ServiceMode
    status: JurisdictionModeApprovalStatus
    approved_at: str | None
    approval_reference: str | None
    evidence_refs: Tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("approval_id", "jurisdiction_code"):
            value = getattr(self, name)
            if not value or value != value.strip():
                raise ValueError(f"{name} is required and must be canonical")
        if not isinstance(self.service_mode, ServiceMode):
            raise TypeError("service_mode must be ServiceMode")
        if not isinstance(self.status, JurisdictionModeApprovalStatus):
            raise TypeError("status must be JurisdictionModeApprovalStatus")
        if not isinstance(self.evidence_refs, tuple) or not self.evidence_refs:
            raise ValueError("jurisdiction approval requires evidence refs")
        if self.status == JurisdictionModeApprovalStatus.APPROVED:
            if not self.approved_at or not self.approval_reference:
                raise ValueError(
                    "approved jurisdiction mode requires approval timestamp and reference"
                )

    @property
    def service_allowed(self) -> bool:
        return self.status == JurisdictionModeApprovalStatus.APPROVED

    @property
    def trading_execution_authority(self) -> bool:
        return False
