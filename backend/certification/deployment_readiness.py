"""Read-only deployment checklist; performs no deployment."""

from __future__ import annotations

from backend.certification.production_readiness_models import (
    CertificationEvidence,
    evaluate_required_evidence,
)

DEPLOYMENT_REQUIREMENTS = (
    "RUNTIME_COMPOSITION",
    "CONFIGURATION",
    "SECRETS",
    "GOVERNANCE",
    "REPORTS",
    "BROKER_RUNTIME",
    "OPTIONS_RUNTIME",
    "MISSION_CONTROL",
    "DASHBOARDS",
)


def evaluate_deployment_readiness(
    evidence: list[CertificationEvidence] | tuple[CertificationEvidence, ...],
    *,
    profile: str | None = None,
) -> dict:
    result = evaluate_required_evidence(
        "DEPLOYMENT_READINESS",
        DEPLOYMENT_REQUIREMENTS,
        evidence,
        profile=profile,
    ).as_dict()
    result.update(
        {
            "deployment_authorized": False,
            "deployment_performed": False,
            "restart_performed": False,
            "execution_allowed": False,
        }
    )
    return result


__all__ = ["DEPLOYMENT_REQUIREMENTS", "evaluate_deployment_readiness"]
