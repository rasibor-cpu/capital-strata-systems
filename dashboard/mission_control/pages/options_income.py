from __future__ import annotations

from dashboard.mission_control.pages._components import detail_table, metric_grid, page_header, section, split_panels


def render(state: dict) -> str:
    options = section(state, "options_income")
    panel = section(state, "options_income_panel")
    return (
        page_header("Options Income", "Read-only Options Income Engine status, opportunities, premium, collateral, Greeks, rolling, and certification.")
        + metric_grid(
            (
                ("Status", options.get("status"), options.get("status")),
                ("Opportunities", len(options.get("opportunities", []) or []), "neutral"),
                ("Certification", options.get("certification"), options.get("certification")),
                ("Operational Readiness", options.get("operational_readiness"), options.get("operational_readiness")),
                ("Assignment Risk", options.get("assignment_risk"), options.get("assignment_risk")),
                ("Volatility Risk", options.get("volatility_risk"), options.get("volatility_risk")),
            )
        )
        + split_panels(
            detail_table("Income Lifecycle", {
                "covered_calls": options.get("covered_calls"),
                "cash_secured_puts": options.get("cash_secured_puts"),
                "paper_positions": options.get("paper_positions"),
                "premium_accounting": options.get("premium_accounting"),
                "collateral": options.get("collateral"),
                "position_health": options.get("position_health"),
            }),
            detail_table("Risk And Allocation", {
                "rolling_recommendations": options.get("rolling_recommendations"),
                "income_targets": options.get("income_targets"),
                "portfolio_allocation": options.get("portfolio_allocation"),
                "greeks": options.get("greeks"),
                "stress_tests": options.get("stress_tests"),
                "alerts": options.get("alerts"),
            }),
            detail_table("Options Income Command Panel", {
                "status": panel.get("status"),
                "deployed": panel.get("deployed"),
                "opportunities": panel.get("opportunities"),
                "premium_accounting": panel.get("premium_accounting"),
                "collateral": panel.get("collateral"),
                "greeks": panel.get("greeks"),
                "assignment_risk": panel.get("assignment_risk"),
                "rolling_recommendations": panel.get("rolling_recommendations"),
                "certification": panel.get("certification"),
                "operational_readiness": panel.get("operational_readiness"),
                "source": panel.get("source"),
                "state_hash": panel.get("state_hash"),
            }),
        )
    )
