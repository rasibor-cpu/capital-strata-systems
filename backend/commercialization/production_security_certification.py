from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class SecurityOperationalApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True, slots=True)
class ProductionSecurityOperationalCertification:
    certification_id: str
    status: SecurityOperationalApprovalStatus
    certified_at: str
    secrets_management_verified: bool
    tls_transport_verified: bool
    access_control_verified: bool
    audit_logging_verified: bool
    monitoring_alerting_verified: bool
    backup_restore_tested: bool
    rollback_tested: bool
    reconciliation_verified: bool
    incident_response_verified: bool
    dependency_vulnerability_reviewed: bool
    reviewer_reference: str
    evidence_refs: Tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "certification_id",
            "certified_at",
            "reviewer_reference",
        ):
            value = getattr(self, name)
            if not value or value != value.strip():
                raise ValueError(f"{name} is required and must be canonical")
        if not isinstance(self.status, SecurityOperationalApprovalStatus):
            raise TypeError("status must be SecurityOperationalApprovalStatus")
        if not isinstance(self.evidence_refs, tuple) or not self.evidence_refs:
            raise ValueError("security certification requires immutable evidence refs")

    @property
    def all_controls_verified(self) -> bool:
        return all(
            (
                self.secrets_management_verified,
                self.tls_transport_verified,
                self.access_control_verified,
                self.audit_logging_verified,
                self.monitoring_alerting_verified,
                self.backup_restore_tested,
                self.rollback_tested,
                self.reconciliation_verified,
                self.incident_response_verified,
                self.dependency_vulnerability_reviewed,
            )
        )

    @property
    def production_security_ready(self) -> bool:
        return (
            self.status == SecurityOperationalApprovalStatus.APPROVED
            and self.all_controls_verified
        )

    @property
    def trading_execution_authority(self) -> bool:
        return False
