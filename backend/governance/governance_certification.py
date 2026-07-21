"""Evidence-only governance certification-readiness engine."""

from __future__ import annotations

from typing import Iterable, Any

from backend.governance.governance_models import (
    EvidenceStatus,
    GovernanceDomain,
    GovernanceEvidence,
)

CERTIFICATION_FACETS = {
    "governance": (GovernanceDomain.COMPLIANCE, "GOVERNANCE"),
    "audit": (GovernanceDomain.AUDIT, "AUDIT"),
    "runtime": (GovernanceDomain.OPERATIONS, "RUNTIME"),
    "identity": (GovernanceDomain.IDENTITY, "IDENTITY"),
    "broker_runtime": (GovernanceDomain.BROKER_RUNTIME, "BROKER_RUNTIME"),
    "options_runtime": (GovernanceDomain.OPTIONS_INCOME, "OPTIONS_RUNTIME"),
    "reporting": (GovernanceDomain.REPORTING, "REPORTING"),
    "security": (GovernanceDomain.SECURITY, "SECURITY"),
    "compliance": (GovernanceDomain.COMPLIANCE, "COMPLIANCE"),
}


def certify_governance_readiness(
    evidence: Iterable[GovernanceEvidence],
) -> dict[str, Any]:
    rows = tuple(evidence)
    checks = {}
    references = {}
    for facet, (domain, control) in CERTIFICATION_FACETS.items():
        match = next(
            (
                row
                for row in rows
                if row.domain is domain
                and str(row.control).upper() == control
                and row.status is EvidenceStatus.PRESENT
                and row.verified
            ),
            None,
        )
        checks[facet] = match is not None
        references[facet] = match.reference if match else None
    return {
        "schema_version": "css.enterprise_governance.certification.v1",
        "status": "READY_FOR_FORMAL_REVIEW"
        if all(checks.values())
        else "EVIDENCE_INCOMPLETE",
        "readiness_percentage": round(
            100.0 * sum(checks.values()) / len(checks), 2
        ),
        "checks": checks,
        "evidence_references": references,
        "blockers": [name for name, passed in checks.items() if not passed],
        "evidence_fabricated": False,
        "formal_certification_claimed": False,
        "production_certified": False,
        "execution_posture": "DISABLED",
        "execution_authority": "BLOCKED",
        "fail_closed": True,
        "advisory_only": True,
        "execution_allowed": False,
    }


__all__ = ["CERTIFICATION_FACETS", "certify_governance_readiness"]
