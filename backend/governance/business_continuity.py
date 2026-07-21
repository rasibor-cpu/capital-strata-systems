"""Read-only business-continuity readiness framework."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable, Any

from backend.governance.governance_models import EvidenceStatus, GovernanceEvidence

BUSINESS_CONTINUITY_CONTROLS = (
    "BACKUP_STATUS",
    "RESTORE_EVIDENCE",
    "DISASTER_RECOVERY_READINESS",
    "RECOVERY_OBJECTIVES",
    "RUNTIME_REDUNDANCY",
    "INFRASTRUCTURE_RESILIENCE",
)


@dataclass(frozen=True)
class RecoveryObjectives:
    recovery_time_objective_minutes: int | None
    recovery_point_objective_minutes: int | None
    owner: str
    last_reviewed: str | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_business_continuity(
    evidence: Iterable[GovernanceEvidence],
    *,
    objectives: RecoveryObjectives | None = None,
) -> dict[str, Any]:
    rows = list(evidence)
    evidence_by_control = {
        str(row.control).upper(): row
        for row in rows
        if row.status is EvidenceStatus.PRESENT and row.verified
    }
    objective_ready = bool(
        objectives
        and objectives.recovery_time_objective_minutes is not None
        and objectives.recovery_time_objective_minutes > 0
        and objectives.recovery_point_objective_minutes is not None
        and objectives.recovery_point_objective_minutes >= 0
        and objectives.owner.strip()
    )
    checks = {}
    references = {}
    for control in BUSINESS_CONTINUITY_CONTROLS:
        passed = objective_ready if control == "RECOVERY_OBJECTIVES" else control in evidence_by_control
        checks[control] = passed
        row = evidence_by_control.get(control)
        references[control] = row.reference if row else None
    satisfied = sum(checks.values())
    return {
        "schema_version": "css.business_continuity.readiness.v1",
        "status": "EVIDENCE_COMPLETE" if all(checks.values()) else "EVIDENCE_INCOMPLETE",
        "percentage": round(100.0 * satisfied / len(checks), 2),
        "checks": checks,
        "evidence_references": references,
        "recovery_objectives": objectives.as_dict() if objectives else None,
        "blockers": [name for name, passed in checks.items() if not passed],
        "formal_certification_claimed": False,
        "read_only": True,
        "execution_allowed": False,
    }


__all__ = [
    "BUSINESS_CONTINUITY_CONTROLS",
    "RecoveryObjectives",
    "assess_business_continuity",
]
