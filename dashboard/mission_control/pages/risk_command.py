from __future__ import annotations

from dashboard.mission_control.pages._components import detail_table, metric_grid, page_header, section, split_panels, warning_banner


def render(state: dict) -> str:
    risk = section(state, "risk")
    command = section(state, "risk_command_center")
    committee = section(state, "risk_committee")
    profit_protection = section(state, "profit_protection_governance")
    return (
        page_header("Risk Command", "Read-only risk, gates, limits, drawdown, exposure, stress, Greeks, margin, and kill-switch visibility.")
        + warning_banner("Risk controls are display-only in MC-001; no limits or gates can be changed here.", status="bad")
        + metric_grid(
            (
                ("Risk State", risk.get("overall_risk_state"), risk.get("overall_risk_state")),
                ("Risk Score", risk.get("risk_score"), "neutral"),
                ("Drawdown", risk.get("drawdown"), "neutral"),
                ("Exposure", risk.get("exposure"), "neutral"),
                ("Unified Gate", risk.get("unified_trade_gate"), risk.get("unified_trade_gate")),
                ("Kill Switch", risk.get("kill_switch"), risk.get("kill_switch")),
            )
        )
        + split_panels(
            detail_table("Limit And Stress", {
                "limit_breaches": risk.get("limit_breaches"),
                "warnings": risk.get("warnings"),
                "stress_tests": risk.get("stress_tests"),
                "capital_limits": risk.get("capital_limits"),
                "daily_session_loss_limits": risk.get("daily_session_loss_limits"),
            }),
            detail_table("Risk Dimensions", {
                "concentration": risk.get("concentration"),
                "liquidity_risk": risk.get("liquidity_risk"),
                "volatility_risk": risk.get("volatility_risk"),
                "greeks": risk.get("greeks"),
                "assignment_exposure": risk.get("assignment_exposure"),
                "collateral_utilization": risk.get("collateral_utilization"),
            }),
            detail_table("Risk Command Projection", {
                "anti_bleed_guard": command.get("anti_bleed_guard"),
                "risk_gates": command.get("risk_gates"),
                "drawdown": command.get("drawdown"),
                "capital_exposure": command.get("capital_exposure"),
                "margin_utilization": command.get("margin_utilization"),
                "var": command.get("var"),
                "greeks": command.get("greeks"),
                "stress_metrics": command.get("stress_metrics"),
                "kill_switch": command.get("kill_switch"),
                "overrides": command.get("overrides"),
                "source": command.get("source"),
                "state_hash": command.get("state_hash"),
            }),
            detail_table("Profit Protection Governance", {
                "status": profit_protection.get("status"),
                "maturity_tier": profit_protection.get("maturity_tier"),
                "approved_banked_net_profit": profit_protection.get("approved_banked_net_profit"),
                "effective_protection_ceiling": profit_protection.get("effective_protection_ceiling"),
                "base_protection_budget": profit_protection.get("base_protection_budget"),
                "adjusted_protection_budget": profit_protection.get("adjusted_protection_budget"),
                "committed_exposure": profit_protection.get("committed_exposure"),
                "reserved_exposure": profit_protection.get("reserved_exposure"),
                "remaining_exposure_capacity": profit_protection.get("remaining_exposure_capacity"),
                "enforcement_status": profit_protection.get("enforcement_status"),
                "reason_codes": profit_protection.get("reason_codes"),
                "data_freshness": profit_protection.get("data_freshness"),
                "execution_allowed": profit_protection.get("execution_allowed"),
                "read_only": profit_protection.get("read_only"),
            }),
            detail_table("Risk Committee", {
                "risk_posture": committee.get("risk_posture"),
                "drawdown": committee.get("drawdown"),
                "concentration": committee.get("concentration"),
                "var": committee.get("var"),
                "stress": committee.get("stress"),
                "anti_bleed_guard": committee.get("anti_bleed_guard"),
                "kill_switch": committee.get("kill_switch"),
                "breaches": committee.get("breaches"),
                "warnings": committee.get("warnings"),
                "links": committee.get("links"),
            }),
        )
    )
