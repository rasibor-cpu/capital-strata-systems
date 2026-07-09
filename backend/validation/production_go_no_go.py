"""
CSS Production Go/No-Go Engine

Consolidates all readiness dimensions and operational acceptance metrics
to compute the final deployment recommendation (GO, CONDITIONAL GO, NO GO).
"""

import time
from typing import Dict, Any, List

class ProductionGoNoGoEngine:
    """
    Consolidated Go/No-Go Decision Engine for CSS production pilot.
    """
    def __init__(
        self,
        readiness_framework: Any = None,
        operational_acceptance: Any = None,
        governance_framework: Any = None
    ):
        self.readiness_framework = readiness_framework
        self.operational_acceptance = operational_acceptance
        self.governance_framework = governance_framework

    def evaluate_decision(self) -> Dict[str, Any]:
        """
        Runs Go/No-Go analysis.
        """
        reasons = []
        status = "NO GO"

        readiness = {}
        if self.readiness_framework:
            readiness = self.readiness_framework.evaluate_readiness()
            
        acceptance = {}
        if self.operational_acceptance:
            acceptance = self.operational_acceptance.validate_acceptance()

        gov = {}
        if self.governance_framework:
            gov = self.governance_framework.check_governance()

        # 1. Retrieve sub-scores and failures
        readiness_score = readiness.get("readiness_score", 0.0)
        critical_readiness = readiness.get("critical_findings", [])
        readiness_warnings = readiness.get("warnings", [])

        acceptance_status = acceptance.get("status", "FAIL")
        acceptance_failures = acceptance.get("failures", [])

        gov_status = gov.get("status", "FAIL")
        gov_blockers = gov.get("blockers", [])

        # 2. Evaluate decision logic
        if critical_readiness or acceptance_failures or gov_blockers or readiness_score < 70.0:
            status = "NO GO"
            if critical_readiness:
                reasons.append(f"Critical readiness findings: {', '.join(critical_readiness)}")
            if acceptance_failures:
                reasons.append(f"Operational acceptance failures: {', '.join(acceptance_failures)}")
            if gov_blockers:
                reasons.append(f"Governance blockers: {', '.join(gov_blockers)}")
            if readiness_score < 70.0:
                reasons.append(f"Readiness score below threshold: {readiness_score:.1f}%")
        elif readiness_warnings or readiness_score < 90.0 or gov_status == "FAIL":
            status = "CONDITIONAL GO"
            if readiness_warnings:
                reasons.append(f"Readiness warnings identified: {', '.join(readiness_warnings)}")
            if readiness_score < 90.0:
                reasons.append(f"Readiness score is slightly degraded: {readiness_score:.1f}%")
            else:
                reasons.append("Governance checklist contains conditional warnings.")
        else:
            status = "GO"
            reasons.append("All canonical checks, operational acceptance criteria, and governance gates passed successfully.")

        return {
            "decision": status,
            "reasons": reasons,
            "readiness_score": readiness_score,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "details": {
                "readiness": readiness,
                "acceptance": acceptance,
                "governance": gov
            }
        }
