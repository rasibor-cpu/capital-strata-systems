"""Single read-only Enterprise Governance subsystem."""

from __future__ import annotations

from typing import Iterable, Any

from backend.governance.business_continuity import (
    RecoveryObjectives,
    assess_business_continuity,
)
from backend.governance.governance_certification import certify_governance_readiness
from backend.governance.governance_models import (
    EvidenceStatus,
    GovernanceDomain,
    GovernanceEvidence,
)
from backend.governance.iso_readiness import assess_iso_27001, assess_iso_9001
from backend.governance.risk_register import EnterpriseRiskRegister


class EnterpriseGovernanceService:
    def __init__(
        self,
        *,
        evidence: Iterable[GovernanceEvidence] = (),
        risks: EnterpriseRiskRegister | None = None,
        recovery_objectives: RecoveryObjectives | None = None,
    ):
        rows = tuple(evidence)
        identifiers = [row.evidence_id for row in rows]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("DUPLICATE_GOVERNANCE_EVIDENCE_ID")
        self._evidence = rows
        self.risks = risks or EnterpriseRiskRegister()
        self.recovery_objectives = recovery_objectives

    def evidence_inventory(self) -> list[dict[str, Any]]:
        return [row.as_dict() for row in self._evidence]

    def snapshot(self) -> dict[str, Any]:
        iso27001 = assess_iso_27001(self._evidence).as_dict()
        iso9001 = assess_iso_9001(self._evidence).as_dict()
        continuity = assess_business_continuity(
            self._evidence,
            objectives=self.recovery_objectives,
        )
        certification = certify_governance_readiness(self._evidence)
        covered_domains = {
            row.domain
            for row in self._evidence
            if row.status is EvidenceStatus.PRESENT and row.verified
        }
        domain_status = {
            domain.value: {
                "evidence_count": sum(row.domain is domain for row in self._evidence),
                "verified_count": sum(
                    row.domain is domain
                    and row.status is EvidenceStatus.PRESENT
                    and row.verified
                    for row in self._evidence
                ),
                "status": "EVIDENCE_PRESENT"
                if domain in covered_domains
                else "EVIDENCE_MISSING",
            }
            for domain in GovernanceDomain
        }
        governance_score = round(
            100.0 * len(covered_domains) / len(GovernanceDomain), 2
        )
        blockers = sorted(
            {
                *(
                    f"ISO27001:{item}" for item in iso27001["blockers"]
                ),
                *(
                    f"ISO9001:{item}" for item in iso9001["blockers"]
                ),
                *(
                    f"CONTINUITY:{item}" for item in continuity["blockers"]
                ),
                *(
                    f"CERTIFICATION:{item}"
                    for item in certification["blockers"]
                ),
            }
        )
        overall = round(
            (
                governance_score
                + iso27001["percentage"]
                + iso9001["percentage"]
                + continuity["percentage"]
                + certification["readiness_percentage"]
            )
            / 5,
            2,
        )
        risk = self.risks.summary()
        return {
            "schema_version": "css.enterprise_governance.v1",
            "overall_certification_readiness": overall,
            "governance_score": governance_score,
            "domains": domain_status,
            "iso_27001": iso27001,
            "iso_9001": iso9001,
            "business_continuity": continuity,
            "enterprise_risk_summary": risk,
            "enterprise_risk_register": self.risks.inventory(),
            "certification": certification,
            "broker_readiness": domain_status["BROKER_RUNTIME"]["status"],
            "runtime_readiness": domain_status["OPERATIONS"]["status"],
            "security_posture": domain_status["SECURITY"]["status"],
            "compliance_posture": domain_status["COMPLIANCE"]["status"],
            "outstanding_blockers": blockers,
            "evidence_inventory": self.evidence_inventory(),
            "formal_certification_claimed": False,
            "production_certified": False,
            "read_only": True,
            "execution_posture": "DISABLED",
            "execution_authority": "BLOCKED",
            "fail_closed": True,
            "advisory_only": True,
            "execution_allowed": False,
        }


__all__ = ["EnterpriseGovernanceService"]
