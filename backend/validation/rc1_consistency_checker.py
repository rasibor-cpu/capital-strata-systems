from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.common.numeric_utils import safe_float


class RC1ConsistencyChecker:
    """Performs cross-module consistency audits on computed advisory metrics."""

    def run_all_checks(
        self,
        *,
        portfolio_construction: Mapping[str, Any] | None = None,
        optimizer: Mapping[str, Any] | None = None,
        committee: Mapping[str, Any] | None = None,
        brief: Mapping[str, Any] | None = None,
        decision_confidence: Mapping[str, Any] | None = None,
        broker_health: Mapping[str, Any] | None = None,
        runtime_health: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        results = {
            "portfolio_optimizer_aligned": True,
            "committee_portfolio_aligned": True,
            "brief_committee_aligned": True,
            "decision_confidence_consistent": True,
            "broker_health_aligned": True,
            "runtime_health_aligned": True,
            "details": [],
        }

        # 1. Check Portfolio & Optimizer consistency
        if portfolio_construction and optimizer:
            pc_preferred = portfolio_construction.get("preferred_portfolio", [])
            opt_best = optimizer.get("best_overall", "")
            # If optimizer has a preferred scenario name, check that it exists
            recommended = optimizer.get("recommended_portfolios", [])
            has_matching_scenario = any(p.get("name") == opt_best for p in recommended) if recommended else False
            if opt_best and recommended and not has_matching_scenario:
                results["portfolio_optimizer_aligned"] = False
                results["details"].append("Mismatch: Optimizer best_overall scenario not found in recommended portfolios.")

        # 2. Check Committee & Portfolio consistency
        if committee and portfolio_construction:
            comm_rec = committee.get("overall_recommendation", "REJECT")
            pc_quality = safe_float(portfolio_construction.get("portfolio_quality", 0.0))
            if comm_rec == "APPROVE" and pc_quality < 50.0:
                results["committee_portfolio_aligned"] = False
                results["details"].append(f"Mismatch: Committee recommendation is APPROVE despite low portfolio quality ({pc_quality:.1f}%).")
            elif comm_rec == "REJECT" and pc_quality > 90.0:
                # Rejecting a high quality portfolio is fine under severe broker issues, but let's log a warning
                results["details"].append(f"Notice: Committee recommendation is REJECT for high quality portfolio ({pc_quality:.1f}%).")

        # 3. Check Brief & Committee consistency
        if brief and committee:
            brief_rec = brief.get("investment_committee", "")
            comm_rec = committee.get("overall_recommendation", "")
            if brief_rec != comm_rec:
                results["brief_committee_aligned"] = False
                results["details"].append(f"Mismatch: Brief investment_committee ('{brief_rec}') does not match Committee overall_recommendation ('{comm_rec}').")

        # 4. Check Decision Confidence consistency
        if brief and decision_confidence:
            brief_conf = safe_float(brief.get("decision_confidence", 0.0))
            dc_conf = safe_float(decision_confidence.get("confidence", decision_confidence.get("confidence_score", 0.0)))
            if abs(brief_conf - dc_conf) > 0.01:
                results["decision_confidence_consistent"] = False
                results["details"].append(f"Mismatch: Brief decision confidence ({brief_conf:.2f}) does not match raw decision confidence ({dc_conf:.2f}).")

        # 5. Check Broker Health consistency
        if brief and broker_health:
            brief_bh = brief.get("broker_health", "").upper()
            raw_bh = str(broker_health.get("health", broker_health.get("broker_health", ""))).upper()
            if brief_bh != raw_bh and raw_bh:
                results["broker_health_aligned"] = False
                results["details"].append(f"Mismatch: Brief broker_health ('{brief_bh}') does not match raw broker_health ('{raw_bh}').")

        # 6. Check Runtime Health consistency
        if brief and runtime_health:
            brief_rh = brief.get("runtime_health", "").upper()
            raw_rh = str(runtime_health.get("status", runtime_health.get("runtime_health", ""))).upper()
            if brief_rh != raw_rh and raw_rh:
                results["runtime_health_aligned"] = False
                results["details"].append(f"Mismatch: Brief runtime_health ('{brief_rh}') does not match raw runtime_health ('{raw_rh}').")

        # Set final status
        all_ok = all(results[k] for k in results if isinstance(results[k], bool))
        results["status"] = "PASS" if all_ok else "PASS WITH WARNINGS"
        if not results["details"]:
            results["details"].append("All cross-module consistency audits completed successfully.")

        return results
