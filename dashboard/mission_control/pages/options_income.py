from __future__ import annotations

from dashboard.mission_control.pages._components import detail_table, metric_grid, page_header, section, warning_banner


def _anchor_panel(anchor: str, content: str) -> str:
    return f'<div class="mc-section-anchor" id="{anchor}">{content}</div>'


def _evidence_panel(anchor: str, title: str, content: str) -> str:
    return (
        f'<div class="mc-section-anchor mc-evidence-disclosure" id="{anchor}">'
        f'<details><summary>{title}</summary>{content}</details>'
        '</div>'
    )


def _nested_value(value, key: str, default="UNAVAILABLE"):
    if isinstance(value, dict):
        result = value.get(key)
        return default if result in (None, "") else result
    return default


def _list_count(value) -> int:
    return len(value) if isinstance(value, list) else 0


def render(state: dict) -> str:
    options = section(state, "options_income")
    panel = section(state, "options_income_panel")
    cert = options.get("certification") if isinstance(options.get("certification"), dict) else {}
    run_rate = options.get("run_rate") if isinstance(options.get("run_rate"), dict) else options.get("income_targets")
    return (
        page_header(
            "Options Income",
            "Phase 178A — advisory data contracts connected. Covered calls, CSPs, premium, collateral, Greeks, rolling, certification. Execution blocked.",
        )
        + warning_banner(
            "ADVISORY ONLY — Execution blocked. No option orders, rolls, assignments, or broker transmissions from this page.",
            status="bad",
        )
        + (
            '<section class="mc-panel" aria-label="Options Income reports">'
            "<h2>Reports</h2>"
            '<p><a class="rc-btn rc-btn-primary" href="/mission-control/reports/viewer?report_code=options_income_executive">'
            "Open paginated Options Income report</a> "
            '<a class="rc-btn" href="/mission-control/reports">Reports hub</a></p>'
            "<p class=\"mc-muted\">All human-facing report links use the shared paginated viewer.</p>"
            "</section>"
        )
        + '<nav class="mc-page-jump" aria-label="Options Income sections">'
          '<a href="#mc-options-status">Status</a>'
          '<a href="#mc-options-lifecycle">Lifecycle</a>'
          '<a href="#mc-options-risk">Risk</a>'
          '<a href="#mc-options-evidence">Evidence</a>'
          '</nav>'
        + metric_grid(
            (
                ("Engine Status", options.get("status"), options.get("status")),
                ("Operational Readiness", options.get("operational_readiness"), options.get("operational_readiness")),
                ("Certification", cert.get("outcome") if cert else options.get("certification"), cert.get("outcome") if cert else options.get("certification")),
                ("Execution", "BLOCKED", "blocked"),
            ),
            css_class="mc-metric-grid mc-metric-grid-priority mc-options-priority",
            aria_label="Options Income priority",
        )
        + metric_grid(
            (
                ("Deployment", options.get("deployment_state") or panel.get("deployment_state"), "neutral"),
                ("Opportunities", options.get("opportunity_count", len(options.get("opportunities", []) or [])), "neutral"),
                ("Data Readiness", (options.get("data_readiness") or {}).get("status") if isinstance(options.get("data_readiness"), dict) else options.get("engine_status"), "neutral"),
                ("Chain / Holdings", _provider_chip(options.get("provider_summary")), "neutral"),
                ("Assignment Risk", _risk_status(options.get("assignment_risk")), "neutral"),
                ("Volatility Risk", _risk_status(options.get("volatility_risk")), "neutral"),
            ),
            css_class="mc-metric-grid mc-metric-grid-secondary",
            aria_label="Options Income secondary metrics",
        )
        + '<div class="mc-operator-stack">'
        + _anchor_panel("mc-options-status", detail_table("Options Income Snapshot", {
            "status": options.get("status"),
            "deployment_state": options.get("deployment_state") or panel.get("deployment_state"),
            "operational_readiness": options.get("operational_readiness"),
            "certification": cert.get("outcome") if cert else options.get("certification"),
            "data_readiness": (options.get("data_readiness") or {}).get("status") if isinstance(options.get("data_readiness"), dict) else options.get("engine_status"),
            "provider": _provider_chip(options.get("provider_summary")),
            "last_successful_refresh": options.get("last_successful_refresh"),
            "execution_blocked": True,
        }))
        + _anchor_panel("mc-options-lifecycle", detail_table("Income Lifecycle Snapshot", {
            "covered_call_count": _list_count(options.get("covered_calls")),
            "cash_secured_put_count": _list_count(options.get("cash_secured_puts")),
            "paper_position_count": _list_count(options.get("paper_positions")),
            "premium_collected": _nested_value(
                _nested_value(options.get("premium_accounting"), "session", {}),
                "premium_collected",
            ),
            "realized_options_income": _nested_value(
                _nested_value(options.get("premium_accounting"), "session", {}),
                "realized_options_income",
            ),
            "collateral_status": _nested_value(options.get("collateral"), "status"),
            "position_health": options.get("position_health") or "UNAVAILABLE",
        }))
        + _anchor_panel("mc-options-risk", detail_table("Risk Snapshot", {
            "assignment_risk": _risk_status(options.get("assignment_risk")),
            "volatility_risk": _risk_status(options.get("volatility_risk")),
            "rolling_recommendations": options.get("rolling_recommendations"),
            "alerts": options.get("alerts"),
        }))
        + _anchor_panel("mc-options-run-rate", detail_table("Run-Rate Snapshot", {
            "target_status": _nested_value(options.get("income_targets"), "status"),
            "monthly_income_target": _nested_value(options.get("income_targets"), "monthly_income_target"),
            "current_month_actual": _nested_value(options.get("income_targets"), "current_month_actual_options_income"),
            "projected_month_end": _nested_value(options.get("income_targets"), "projected_month_end_options_income"),
            "run_rate_status": _nested_value(run_rate, "status"),
            "portfolio_id": _nested_value(options.get("portfolio_allocation"), "portfolio_id"),
            "capital_allocated": _nested_value(options.get("portfolio_allocation"), "capital_allocated"),
            "available_capital": _nested_value(options.get("portfolio_allocation"), "available_capital"),
            "missing_dependencies": ", ".join(options.get("missing_dependencies", []))
                if isinstance(options.get("missing_dependencies"), list) and options.get("missing_dependencies")
                else "NONE RECORDED",
        }))
        + _evidence_panel("mc-options-evidence", "Show full options-income command evidence", detail_table("Options Income Command Panel (Full)", {
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
        }))
        + _evidence_panel("mc-options-greeks", "Show Greeks and stress-test evidence", detail_table("Greeks & Stress Tests", {
            "greeks": options.get("greeks"),
            "stress_tests": options.get("stress_tests"),
        }))
        + _evidence_panel("mc-options-provider", "Show provider/readiness evidence", detail_table("Provider & Data Readiness", {
            "data_readiness": options.get("data_readiness"),
            "provider_summary": options.get("provider_summary"),
        }))
        + _evidence_panel("mc-options-accounting", "Show premium/collateral/allocation evidence", detail_table("Premium Accounting", options.get("premium_accounting", {})) + detail_table("Collateral", options.get("collateral", {})) + detail_table("Income Targets / Run Rate", {
            "income_targets": options.get("income_targets"),
            "run_rate": run_rate,
            "portfolio_allocation": options.get("portfolio_allocation"),
        }))
        + '</div>'
    )


def _risk_status(value) -> str:
    if isinstance(value, dict):
        return str(value.get("status") or value.get("detail") or "UNAVAILABLE")
    return str(value or "UNAVAILABLE")


def _provider_chip(summary) -> str:
    if not isinstance(summary, dict):
        return "NOT_CONFIGURED"
    chain = summary.get("option_chain_status") or summary.get("readiness_status") or "UNKNOWN"
    holdings = summary.get("holdings_status") or "UNKNOWN"
    return f"{chain} / {holdings}"
