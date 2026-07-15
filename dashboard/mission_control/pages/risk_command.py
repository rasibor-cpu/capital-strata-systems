from __future__ import annotations

from dashboard.mission_control.pages._components import detail_table, metric_grid, page_header, section, split_panels, warning_banner


def render(state: dict) -> str:
    risk = section(state, "risk")
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
        )
    )
