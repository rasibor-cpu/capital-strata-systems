from __future__ import annotations

from dashboard.mission_control.pages._components import detail_table, metric_grid, page_header, section, split_panels, warning_banner


def render(state: dict) -> str:
    options = section(state, "options_income")
    panel = section(state, "options_income_panel")
    cert = options.get("certification") if isinstance(options.get("certification"), dict) else {}
    run_rate = options.get("run_rate") if isinstance(options.get("run_rate"), dict) else options.get("income_targets")
    return (
        page_header(
            "Options Income",
            "Phase 177D — canonical Options Income Engine (advisory). Covered calls, CSPs, premium, collateral, Greeks, rolling, certification.",
        )
        + warning_banner(
            "ADVISORY ONLY — Execution blocked. No option orders, rolls, assignments, or broker transmissions from this page.",
            status="bad",
        )
        + metric_grid(
            (
                ("Engine Status", options.get("status"), options.get("status")),
                ("Deployment", options.get("deployment_state") or panel.get("deployment_state"), "neutral"),
                ("Opportunities", options.get("opportunity_count", len(options.get("opportunities", []) or [])), "neutral"),
                ("Certification", cert.get("outcome") if cert else options.get("certification"), "neutral"),
                ("Operational Readiness", options.get("operational_readiness"), options.get("operational_readiness")),
                ("Assignment Risk", _risk_status(options.get("assignment_risk")), "neutral"),
                ("Volatility Risk", _risk_status(options.get("volatility_risk")), "neutral"),
                ("Last Refresh", options.get("last_successful_refresh"), "neutral"),
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
            detail_table("Targets / Run-Rate / Allocation", {
                "income_targets": options.get("income_targets"),
                "run_rate": run_rate,
                "portfolio_allocation": options.get("portfolio_allocation"),
                "missing_dependencies": options.get("missing_dependencies"),
            }),
            detail_table("Risk And Rolling", {
                "rolling_recommendations": options.get("rolling_recommendations"),
                "greeks": options.get("greeks"),
                "assignment_risk": options.get("assignment_risk"),
                "volatility_risk": options.get("volatility_risk"),
                "stress_tests": options.get("stress_tests"),
                "alerts": options.get("alerts"),
            }),
            detail_table("Options Income Command Panel", {
                "status": panel.get("status"),
                "deployed": panel.get("deployed"),
                "deployment_state": panel.get("deployment_state"),
                "opportunity_count": panel.get("opportunity_count"),
                "opportunities": panel.get("opportunities"),
                "premium_accounting": panel.get("premium_accounting"),
                "collateral": panel.get("collateral"),
                "greeks": panel.get("greeks"),
                "assignment_risk": panel.get("assignment_risk"),
                "volatility_risk": panel.get("volatility_risk"),
                "rolling_recommendations": panel.get("rolling_recommendations"),
                "income_targets": panel.get("income_targets"),
                "run_rate": panel.get("run_rate"),
                "certification": panel.get("certification"),
                "operational_readiness": panel.get("operational_readiness"),
                "missing_dependencies": panel.get("missing_dependencies"),
                "source": panel.get("source"),
                "provenance": panel.get("provenance") or options.get("provenance"),
                "state_hash": panel.get("state_hash") or options.get("state_hash"),
                "generated_at": panel.get("generated_at") or options.get("generated_at"),
                "last_successful_refresh": panel.get("last_successful_refresh"),
                "advisory_only": True,
                "execution_blocked": True,
            }),
        )
    )


def _risk_status(value) -> str:
    if isinstance(value, dict):
        return str(value.get("status") or value.get("detail") or "UNAVAILABLE")
    return str(value or "UNAVAILABLE")
