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
    *,
    profile: str | None = None,
    drill_observation: dict | None = None,
) -> dict:
    result = evaluate_required_evidence(
        "DISASTER_RECOVERY_READINESS",
        DISASTER_RECOVERY_REQUIREMENTS,
        evidence,
        profile=profile,
    ).as_dict()
    backup_performed = False
    restore_performed = False
    rto_seconds = None
    rpo_seconds = None
    drill = drill_observation if isinstance(drill_observation, dict) else {}
    if (
        drill.get("backup_performed") is True
        and drill.get("restore_performed") is True
        and drill.get("ok") is True
    ):
        backup_performed = True
        restore_performed = True
        if "rto_seconds" in drill:
            rto_seconds = drill.get("rto_seconds")
        if "rpo_seconds" in drill:
            rpo_seconds = drill.get("rpo_seconds")
    payload = {
        "backup_performed": backup_performed,
        "restore_performed": restore_performed,
        "recovery_invoked": False,
        "execution_allowed": False,
    }
    if rto_seconds is not None:
        payload["rto_seconds"] = rto_seconds
    if rpo_seconds is not None:
        payload["rpo_seconds"] = rpo_seconds
    result.update(payload)
    return result


__all__ = [
    "DISASTER_RECOVERY_REQUIREMENTS",
    "evaluate_disaster_recovery_readiness",
]
