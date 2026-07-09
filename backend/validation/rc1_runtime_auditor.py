from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from backend.common.numeric_utils import safe_float


class RC1RuntimeAuditor:
    """Audits the environment for missing modules, exceptions, invalid value boundaries, and import integrity."""

    def perform_audit(
        self,
        *,
        portfolio_construction: Mapping[str, Any] | None = None,
        committee: Mapping[str, Any] | None = None,
        brief: Mapping[str, Any] | None = None,
        decision_confidence: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        audit_errors = []
        audit_warnings = []

        # 1. Dependency and Module Imports Integrity Check
        try:
            from backend.reporting.executive_decision_brief import ExecutiveDecisionBrief  # noqa: F401
            from backend.portfolio.portfolio_construction_intelligence import PortfolioConstructionIntelligenceEngine  # noqa: F401
            from backend.intelligence.investment_committee_engine import InvestmentCommitteeEngine  # noqa: F401
        except ImportError as exc:
            audit_errors.append(f"Broken Dependency: Critical module failed to import: {exc}")

        # 2. Audit Portfolio Construction values
        if portfolio_construction:
            pc_status = portfolio_construction.get("status", "")
            if pc_status not in {"OK", "PARTIAL", "DEFENSIVE", "DATA UNAVAILABLE"}:
                audit_warnings.append(f"Invalid Status: Portfolio construction status '{pc_status}' is unusual.")
            quality = portfolio_construction.get("portfolio_quality")
            if quality is None:
                audit_warnings.append("Unexpected None: portfolio_quality is missing.")
            else:
                q_val = safe_float(quality)
                if q_val < 0.0 or q_val > 100.0 or not math.isfinite(q_val):
                    audit_errors.append(f"Boundary Violation: Portfolio quality '{quality}' is out of range [0, 100].")

        # 3. Audit Committee values
        if committee:
            comm_status = committee.get("status", "")
            if comm_status not in {"OK", "DATA UNAVAILABLE"}:
                audit_warnings.append(f"Invalid Status: Committee status '{comm_status}' is unusual.")
            rec = committee.get("overall_recommendation")
            if rec not in {"APPROVE", "CONDITIONAL", "REJECT", "NEEDS_REVIEW"}:
                audit_warnings.append(f"Invalid Value: Committee recommendation '{rec}' is outside standard vocabulary.")
            vote = committee.get("committee_vote", {})
            if not isinstance(vote, Mapping):
                audit_errors.append("Type Mismatch: Committee vote tally must be a mapping dictionary.")
            else:
                for k in ["approve", "conditional", "reject"]:
                    if k not in vote:
                        audit_warnings.append(f"Missing Field: Committee vote tally key '{k}' is missing.")
                    else:
                        v_val = safe_float(vote[k])
                        if v_val < 0 or not math.isfinite(v_val):
                            audit_errors.append(f"Boundary Violation: Vote count '{vote[k]}' for '{k}' is invalid.")

        # 4. Audit Decision Confidence values
        if decision_confidence:
            conf = decision_confidence.get("confidence", decision_confidence.get("confidence_score"))
            if conf is None:
                audit_warnings.append("Unexpected None: confidence is missing.")
            else:
                c_val = safe_float(conf)
                if c_val < 0.0 or c_val > 100.0 or not math.isfinite(c_val):
                    audit_errors.append(f"Boundary Violation: Decision confidence '{conf}' is out of range [0, 100].")

        # 5. Audit Brief values
        if brief:
            brief_status = brief.get("overall_status", "")
            if brief_status not in {"GREEN", "AMBER", "RED", "DEFENSIVE", "DATA UNAVAILABLE"}:
                audit_warnings.append(f"Invalid Status: Brief overall status '{brief_status}' is invalid.")
            # Check safety override constraints are present
            exec_status = brief.get("execution_status", {})
            if exec_status.get("execution_authority") != "NOT GRANTED":
                audit_errors.append("Safety Gate Violated: execution_authority is not locked to 'NOT GRANTED' in brief.")
            if exec_status.get("live_trading") != "BLOCKED":
                audit_errors.append("Safety Gate Violated: live_trading is not locked to 'BLOCKED' in brief.")
            if exec_status.get("broker_execution") != "DISARMED":
                audit_errors.append("Safety Gate Violated: broker_execution is not locked to 'DISARMED' in brief.")

        # Determine final status
        if audit_errors:
            status = "FAIL"
        elif audit_warnings:
            status = "PASS WITH WARNINGS"
        else:
            status = "PASS"

        return {
            "status": status,
            "errors": audit_errors,
            "warnings": audit_warnings,
            "details": ["Audit completed successfully."] if not audit_errors and not audit_warnings else []
        }
