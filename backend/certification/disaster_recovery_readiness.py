"""Disaster recovery governance-evidence readiness."""

from __future__ import annotations

from backend.certification.production_readiness_models import (
    CertificationEvidence,
    evaluate_required_evidence,
)

DISASTER_RECOVERY_REQUIREMENTS = (
    "BACKUPS",
    "RESTORE_PROCEDURES",
    "RECOVERY_OBJECTIVES",
    "REDUNDANCY",
    "RUNTIME_RESILIENCE",
    "CONFIGURATION_RECOVERY",
)


def evaluate_disaster_recovery_readiness(
    evidence: list[CertificationEvidence] | tuple[CertificationEvidence, ...],
) -> dict:
    result = evaluate_required_evidence(
        "DISASTER_RECOVERY_READINESS",
        DISASTER_RECOVERY_REQUIREMENTS,
        evidence,
    ).as_dict()
    result.update(
        {
            "backup_performed": False,
            "restore_performed": False,
            "recovery_invoked": False,
            "execution_allowed": False,
        }
    )
    return result


__all__ = [
    "DISASTER_RECOVERY_REQUIREMENTS",
    "evaluate_disaster_recovery_readiness",
]
