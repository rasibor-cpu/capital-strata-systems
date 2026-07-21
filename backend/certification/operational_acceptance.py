"""Operational Acceptance Testing evidence evaluator."""

from __future__ import annotations

from backend.certification.production_readiness_models import (
    CertificationEvidence,
    evaluate_required_evidence,
)

OAT_REQUIREMENTS = (
    "STARTUP",
    "SHUTDOWN",
    "RECOVERY",
    "RUNTIME_HEALTH",
    "CONFIGURATION_VALIDATION",
    "DEPENDENCY_VALIDATION",
    "REPORT_GENERATION",
    "DASHBOARD_RENDERING",
    "CERTIFICATION_EVIDENCE",
)


def evaluate_operational_acceptance(
    evidence: list[CertificationEvidence] | tuple[CertificationEvidence, ...],
) -> dict:
    result = evaluate_required_evidence(
        "OPERATIONAL_ACCEPTANCE",
        OAT_REQUIREMENTS,
        evidence,
    ).as_dict()
    result.update(
        {
            "restart_performed": False,
            "shutdown_performed": False,
            "deployment_performed": False,
            "advisory_only": True,
            "execution_allowed": False,
        }
    )
    return result


__all__ = ["OAT_REQUIREMENTS", "evaluate_operational_acceptance"]
