"""Phase 181 evidence-only controlled-deployment certification engine."""

from __future__ import annotations

from typing import Any, Mapping

from backend.certification.deployment_readiness import evaluate_deployment_readiness
from backend.certification.disaster_recovery_readiness import (
    evaluate_disaster_recovery_readiness,
)
from backend.certification.endurance_readiness import evaluate_endurance_readiness
from backend.certification.evidence_authority import authority_diagnostics
from backend.certification.operational_acceptance import (
    evaluate_operational_acceptance,
)
from backend.certification.production_readiness_models import (
    CertificationEvidence,
    evaluate_required_evidence,
)

PLATFORM_REQUIREMENTS = (
    "ENTERPRISE_IDENTITY_RUNTIME",
    "ENTERPRISE_SECRET_RUNTIME",
    "ENTERPRISE_OAUTH_RUNTIME",
    "ENTERPRISE_BROKER_RUNTIME",
    "ENTERPRISE_GOVERNANCE",
    "ENTERPRISE_REPORTING",
    "MISSION_CONTROL",
    "RUNTIME_STATUS",
    "OPTIONS_INCOME_ADVISORY_RUNTIME",
)


class ProductionReadinessCertificationEngine:
    def __init__(
        self,
        *,
        evidence: list[CertificationEvidence] | tuple[CertificationEvidence, ...],
        governance_snapshot: Mapping[str, Any] | None = None,
        profile: str | None = None,
    ):
        self.evidence = tuple(evidence)
        self.governance = dict(governance_snapshot or {})
        self.profile = profile

    def evaluate(self, *, profile: str | None = None) -> dict[str, Any]:
        resolved = profile if profile is not None else self.profile
        platform = evaluate_required_evidence(
            "PLATFORM_CERTIFICATION",
            PLATFORM_REQUIREMENTS,
            self.evidence,
            profile=resolved,
        ).as_dict()
        oat = evaluate_operational_acceptance(self.evidence, profile=resolved)
        endurance = evaluate_endurance_readiness(self.evidence, profile=resolved)
        disaster_recovery = evaluate_disaster_recovery_readiness(
            self.evidence, profile=resolved
        )
        deployment = evaluate_deployment_readiness(self.evidence, profile=resolved)
        frameworks = (platform, oat, endurance, disaster_recovery, deployment)
        score = round(
            sum(float(row["percentage"]) for row in frameworks) / len(frameworks),
            2,
        )
        blockers = sorted(
            {
                f"{row['framework']}:{blocker}"
                for row in frameworks
                for blocker in row["blockers"]
            }
        )
        evidence_complete = all(row["evidence_complete"] for row in frameworks)
        governance_score = float(self.governance.get("governance_score") or 0)
        risks = self.governance.get("enterprise_risk_summary")
        risks = risks if isinstance(risks, Mapping) else {}
        authority = authority_diagnostics(resolved)
        return {
            "schema_version": "css.production_readiness.certification.v1",
            "status": "CERTIFIED_FOR_CONTROLLED_DEPLOYMENT"
            if evidence_complete and not blockers
            else "NOT_CERTIFIED",
            "certification_score": score,
            "governance_score": governance_score,
            "certification_profile": authority["certification_profile"],
            "evidence_authority": authority,
            "platform_certification": platform,
            "operational_acceptance": oat,
            "endurance_readiness": endurance,
            "disaster_recovery_readiness": disaster_recovery,
            "deployment_readiness": deployment,
            "broker_readiness": _requirement_status(
                platform, "ENTERPRISE_BROKER_RUNTIME"
            ),
            "runtime_readiness": _requirement_status(platform, "RUNTIME_STATUS"),
            "deployment_blockers": blockers,
            "outstanding_risks": dict(risks),
            "evidence_completeness": score,
            "evidence_inventory": [row.as_dict() for row in self.evidence],
            "evidence_fabricated": False,
            "deployment_authorized": False,
            "deployment_performed": False,
            "production_trading_certified": False,
            "execution_posture": "DISABLED",
            "execution_authority": "BLOCKED",
            "fail_closed": True,
            "advisory_only": True,
            "execution_allowed": False,
        }


def _requirement_status(result: Mapping[str, Any], requirement: str) -> str:
    row = next(
        (
            check
            for check in result.get("checks", [])
            if check.get("requirement") == requirement
        ),
        None,
    )
    return str((row or {}).get("status") or "EVIDENCE_MISSING")


__all__ = [
    "PLATFORM_REQUIREMENTS",
    "ProductionReadinessCertificationEngine",
]
