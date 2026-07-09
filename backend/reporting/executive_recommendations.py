from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.common.numeric_utils import safe_float
from backend.common.status_types import GREEN, AMBER, RED, UNKNOWN, FAIL
from backend.common.constants import (
    CONFIDENCE_WARNING_THRESHOLD,
    CONFIDENCE_CRITICAL_THRESHOLD,
    PORTFOLIO_DRAWDOWN_WARNING_THRESHOLD,
    PORTFOLIO_CONCENTRATION_WARNING_THRESHOLD,
)


class ExecutiveRecommendations:
    """Consolidate and filter risks, opportunities, actions, and warnings from CSS payloads."""

    def extract_risks(
        self,
        *,
        portfolio_construction: Mapping[str, Any] | None = None,
        broker_health: Mapping[str, Any] | None = None,
        runtime_health: Mapping[str, Any] | None = None,
        decision_confidence: Mapping[str, Any] | None = None,
        committee: Mapping[str, Any] | None = None,
    ) -> list[str]:
        risks = []

        # 1. Check Broker Health
        bh = broker_health or {}
        brokers_status = bh.get("brokers", {})
        if not brokers_status and isinstance(bh.get("health"), str):
            # Single broker fallback
            broker_name = bh.get("broker", UNKNOWN).upper()
            health_state = bh.get("health", UNKNOWN).upper()
            if health_state in {RED, AMBER, FAIL}:
                risks.append(f"Broker {broker_name} status is degraded ({health_state}).")
        else:
            for name, details in brokers_status.items():
                health = str(details.get("health", details.get("status", GREEN))).upper()
                if health in {RED, AMBER, FAIL}:
                    risks.append(f"Broker {name} is reporting degraded health ({health}).")

        # 2. Check Runtime Health
        rh = runtime_health or {}
        rh_status = str(rh.get("status", rh.get("runtime_health", rh.get("overall_operational_health", GREEN)))).upper()
        if rh_status in {RED, AMBER, FAIL, "DEGRADED"}:
            risks.append(f"System runtime health is currently degraded ({rh_status}).")
        
        # 3. Check Decision Confidence
        dc = decision_confidence or {}
        conf = safe_float(dc.get("confidence", dc.get("confidence_score", 100.0)))
        if conf < CONFIDENCE_WARNING_THRESHOLD:
            risks.append(f"Decision confidence is below warning threshold at {conf:.1f}%.")

        # 4. Check Portfolio parameters
        pc = portfolio_construction or {}
        dd = safe_float(pc.get("expected_drawdown", 0.0))
        if dd > PORTFOLIO_DRAWDOWN_WARNING_THRESHOLD:
            risks.append(f"Portfolio expected drawdown is elevated at {dd:.1f}%.")

        con = safe_float(pc.get("diversification_optimization", {}).get("concentration_score", 0.0))
        if con > PORTFOLIO_CONCENTRATION_WARNING_THRESHOLD:
            risks.append(f"Portfolio asset concentration is high ({con:.1f}%).")

        # 5. Check Committee Warnings
        comm = committee or {}
        tally = comm.get("committee_vote", {})
        if tally.get("reject", 0) > 0:
            risks.append(f"Investment committee has {tally['reject']} rejection vote(s).")
        if tally.get("conditional", 0) > 2:
            risks.append("Investment committee has high volume of conditional approvals.")

        # Clean duplicates
        unique_risks = sorted(list(set(risks)))
        return unique_risks or ["No high priority risks identified at this time."]

    def extract_opportunities(
        self,
        *,
        portfolio_construction: Mapping[str, Any] | None = None,
        optimizer: Mapping[str, Any] | None = None,
    ) -> list[str]:
        opportunities = []

        # 1. Opportunities from construction ranking
        pc = portfolio_construction or {}
        for opp in pc.get("ranked_opportunities", []):
            opp_id = opp.get("symbol", opp.get("opportunity_id", UNKNOWN))
            ret = safe_float(opp.get("expected_return", 0.0))
            if ret > 15.0:
                opportunities.append(f"High-yield opportunity: {opp_id} (Expected Return: {ret:.1f}%).")

        # 2. Opportunities from optimization scenarios
        opt = optimizer or {}
        portfolios = opt.get("recommended_portfolios", [])
        for p in portfolios:
            p_name = p.get("name", UNKNOWN)
            ret = safe_float(p.get("expected_return", 0.0))
            quality = safe_float(p.get("quality_score", 0.0))
            if quality > 90.0:
                opportunities.append(f"High-quality portfolio configuration: {p_name} (Quality: {quality:.1f}%, Return: {ret:.1f}%).")

        unique_opps = sorted(list(set(opportunities)))
        return unique_opps or ["No premium tactical opportunities identified."]

    def generate_recommended_actions(
        self,
        *,
        overall_status: str,
        portfolio_construction: Mapping[str, Any] | None = None,
        committee: Mapping[str, Any] | None = None,
        broker_health: Mapping[str, Any] | None = None,
    ) -> list[str]:
        actions = []

        # Standard advisory recommendations
        pc = portfolio_construction or {}
        preferred = pc.get("preferred_portfolio", [])
        if preferred:
            symbols = [item.get("symbol", item.get("opportunity_id", "Asset")) for item in preferred]
            actions.append(f"Deploy advisory capital allocation to preferred assets: {', '.join(symbols)}.")
        else:
            actions.append("Rebalance portfolio to match the target strategic scenario.")

        # Check broker status issues
        bh = broker_health or {}
        brokers_status = bh.get("brokers", {})
        degraded_brokers = []
        if not brokers_status and isinstance(bh.get("health"), str):
            if bh.get("health", GREEN).upper() in {RED, AMBER, FAIL}:
                degraded_brokers.append(bh.get("broker", UNKNOWN))
        else:
            for name, details in brokers_status.items():
                health = str(details.get("health", details.get("status", GREEN))).upper()
                if health in {RED, AMBER, FAIL}:
                    degraded_brokers.append(name)
        if degraded_brokers:
            actions.append(f"Remediate degraded connectivity status on: {', '.join(degraded_brokers)}.")

        # Check Committee Recommendation
        comm = committee or {}
        rec = comm.get("overall_recommendation", "APPROVE")
        if rec in {RED, "NEEDS_REVIEW", "CONDITIONAL"}:
            actions.append("Conduct detailed committee review to address compliance or risk parameters.")
        
        # Overall status dependent
        if overall_status == "DEFENSIVE":
            actions.append("Increase defensive allocations (fixed income/cash) to mitigate regime risk.")
        elif overall_status == AMBER:
            actions.append("Optimize portfolio weights to improve diversification scores.")

        unique_actions = sorted(list(set(actions)))
        return unique_actions

    def generate_operational_warnings(
        self,
        *,
        broker_health: Mapping[str, Any] | None = None,
        runtime_health: Mapping[str, Any] | None = None,
        decision_confidence: Mapping[str, Any] | None = None,
    ) -> list[str]:
        warnings = []

        # 1. Broker Warnings
        bh = broker_health or {}
        brokers_status = bh.get("brokers", {})
        if not brokers_status and isinstance(bh.get("health"), str):
            health = bh.get("health", GREEN).upper()
            if health == RED:
                warnings.append(f"CRITICAL: Broker {bh.get('broker', UNKNOWN).upper()} connectivity is offline.")
            elif health == AMBER:
                warnings.append(f"WARNING: Broker {bh.get('broker', UNKNOWN).upper()} connectivity is degraded.")
        else:
            for name, details in brokers_status.items():
                health = str(details.get("health", details.get("status", GREEN))).upper()
                if health == RED:
                    warnings.append(f"CRITICAL: Broker {name} connectivity is offline.")
                elif health == AMBER:
                    warnings.append(f"WARNING: Broker {name} connectivity is degraded.")

        # 2. Runtime Warnings
        rh = runtime_health or {}
        rh_status = str(rh.get("status", rh.get("runtime_health", rh.get("overall_operational_health", GREEN)))).upper()
        if rh_status == RED:
            warnings.append("CRITICAL: Runtime supervisor reports system engine failure.")
        elif rh_status == AMBER or rh_status == "DEGRADED":
            warnings.append("WARNING: Runtime supervisor reports degraded system operational health.")

        # 3. Decision Confidence Warnings
        dc = decision_confidence or {}
        conf = safe_float(dc.get("confidence", dc.get("confidence_score", 100.0)))
        if conf < CONFIDENCE_CRITICAL_THRESHOLD:
            warnings.append(f"CRITICAL: Statistical model confidence is dangerously low ({conf:.1f}%).")
        elif conf < CONFIDENCE_WARNING_THRESHOLD:
            warnings.append(f"WARNING: Statistical model confidence is slightly low ({conf:.1f}%).")

        return warnings
