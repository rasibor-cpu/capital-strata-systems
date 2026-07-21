"""Endurance readiness from observed evidence only."""

from __future__ import annotations

from backend.certification.production_readiness_models import (
    CertificationEvidence,
    evaluate_required_evidence,
)

ENDURANCE_REQUIREMENTS = (
    "MEMORY_STABILITY",
    "RESOURCE_UTILISATION",
    "RUNTIME_HEALTH",
    "EVENT_PROCESSING",
    "REPORT_GENERATION",
    "DASHBOARD_REFRESH",
    "CERTIFICATION_REFRESH",
)


def evaluate_endurance_readiness(
    evidence: list[CertificationEvidence] | tuple[CertificationEvidence, ...],
) -> dict:
    result = evaluate_required_evidence(
        "ENDURANCE_READINESS",
        ENDURANCE_REQUIREMENTS,
        evidence,
    ).as_dict()
    result.update(
        {
            "synthetic_performance_claims": False,
            "performance_evidence_complete": result["evidence_complete"],
            "execution_allowed": False,
        }
    )
    return result


__all__ = ["ENDURANCE_REQUIREMENTS", "evaluate_endurance_readiness"]
