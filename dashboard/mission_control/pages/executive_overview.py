from __future__ import annotations

from dashboard.mission_control.pages._components import (
    detail_table,
    escape,
    metric_grid,
    page_header,
    section,
    split_panels,
    warning_banner,
)
from backend.reporting.executive_brief_readiness_orchestrator import (
    ExecutiveBriefReadinessOrchestrator,
    evidence_from_mission_control_state,
)
from backend.executive_reporting.service import ExecutiveFinancialReportingService
from backend.executive_decision_intelligence.service import ExecutiveDecisionIntelligenceService


def _edi_state_class(state: str) -> str:
    token = str(state or "").strip().upper()
    if token == "STABLE":
        return "good"
    if token == "ATTENTION":
        return "warn"
    if token in {"STRESSED", "NOT_READY", "DEGRADED"}:
        return "bad"
    return "neutral"


def _executive_decision_intelligence_card(state: dict) -> str:
    """Phase 179 — Executive Decision Intelligence card (orchestration only; no P&L math)."""
    try:
        service = ExecutiveDecisionIntelligenceService()
        summary = service.summary(state)
        exec_state = str(summary.get("executive_state") or "DEGRADED")
        state_cls = _edi_state_class(exec_state)
        conf = summary.get("confidence") if isinstance(summary.get("confidence"), dict) else {}
        conf_band = str(conf.get("confidence_band") or "VERY_LOW")
        conf_val = conf.get("overall_confidence")
        next_action = summary.get("recommended_next_action")
        if isinstance(next_action, dict):
            next_text = str(next_action.get("title") or "—")
        else:
            next_text = str(summary.get("recommended_executive_focus") or "—")
        generated = str(summary.get("generated_at") or "—")

        def _list_rows(items: object, limit: int = 5) -> str:
            rows = []
            if isinstance(items, list):
                for entry in items[:limit]:
                    if isinstance(entry, dict):
                        title = escape(str(entry.get("title") or entry.get("code") or "—"))
                        pri = escape(str(entry.get("priority") or ""))
                        rows.append(f"<li><strong>{pri}</strong> {title}</li>")
            if not rows:
                rows.append("<li>—</li>")
            return "<ol>" + "".join(rows) + "</ol>"

        return (
            '<section class="mc-panel" id="executive-decision-intelligence" '
            'aria-label="Executive Decision Intelligence" '
            'data-phase="179" data-advisory-only="true" data-trading-impact="false" '
            f'data-executive-state="{escape(exec_state)}">'
            "<h2>Executive Decision Intelligence</h2>"
            '<p class="mc-muted">Advisory orchestration of Phase 176J/177/178 and Mission Control signals. '
            "Does not recalculate financial statements. No trading or execution impact.</p>"
            "<table>"
            f"<tr><th>Overall Executive State</th><td>"
            f'<em class="mc-status {state_cls}">{escape(exec_state)}</em></td></tr>'
            f"<tr><th>Confidence</th><td>{escape(conf_band)} ({escape(str(conf_val if conf_val is not None else '—'))})</td></tr>"
            f"<tr><th>Recommended Next Action</th><td>{escape(next_text)}</td></tr>"
            f"<tr><th>Generated</th><td>{escape(generated)}</td></tr>"
            "</table>"
            "<h3>Top Priorities</h3>"
            + _list_rows(summary.get("top_five_priorities"))
            + "<h3>Top Risks</h3>"
            + _list_rows(summary.get("top_risks"), 3)
            + "<h3>Top Opportunities</h3>"
            + _list_rows(summary.get("top_opportunities"), 3)
            + '<p class="mc-muted">'
            '<a href="/api/executive-decision-intelligence/summary">GET /api/executive-decision-intelligence/summary</a>'
            " · "
            '<a href="/api/executive-decision-intelligence/scorecard">GET /api/executive-decision-intelligence/scorecard</a>'
            "</p>"
            "</section>"
        )
    except Exception as exc:  # noqa: BLE001 — never fail EO for EDI
        return (
            '<section class="mc-panel" id="executive-decision-intelligence" '
            'aria-label="Executive Decision Intelligence" '
            'data-phase="179" data-advisory-only="true" data-trading-impact="false" '
            'data-executive-state="DEGRADED">'
            "<h2>Executive Decision Intelligence</h2>"
            '<p class="mc-muted">Advisory EDI temporarily unavailable. Existing Executive Overview cards remain active.</p>'
            "<table>"
            '<tr><th>Overall Executive State</th><td><em class="mc-status bad">DEGRADED</em></td></tr>'
            "<tr><th>Confidence</th><td>—</td></tr>"
            "<tr><th>Recommended Next Action</th><td>—</td></tr>"
            "<tr><th>Generated</th><td>—</td></tr>"
            "</table>"
            f'<p class="mc-muted">{escape(type(exc).__name__)} during local evaluation</p>'
            '<p class="mc-muted"><a href="/api/executive-decision-intelligence/summary">'
            "GET /api/executive-decision-intelligence/summary</a></p>"
            "</section>"
        )


def _readiness_state_class(state: str) -> str:
    """Map readiness states distinctly (avoid status_class treating NOT_READY as good)."""
    token = str(state or "").strip().upper().replace("-", "_")
    if token == "GREEN":
        return "good"
    if token == "AMBER":
        return "warn"
    if token in {"RED", "NOT_READY"}:
        return "bad"
    # NOT_AVAILABLE and unknown tokens must never render as green
    if token == "NOT_AVAILABLE":
        return "neutral"
    return "neutral"


def _executive_brief_readiness_card(state: dict) -> str:
    """Phase 176J — advisory Executive Brief readiness card (read-only)."""
    try:
        orch = ExecutiveBriefReadinessOrchestrator()
        report = orch.generate_report(evidence=evidence_from_mission_control_state(state))
        missing = list(report.missing_datasets or [])
        warnings = list(report.warning_items or [])
        missing_txt = ", ".join(str(x) for x in missing[:8]) if missing else "None"
        if len(missing) > 8:
            missing_txt += f" (+{len(missing) - 8} more)"
        warnings_txt = "; ".join(str(x) for x in warnings[:5]) if warnings else "None"
        if len(warnings) > 5:
            warnings_txt += f" (+{len(warnings) - 5} more)"
        score_txt = f"{report.score:.1f}" if isinstance(report.score, (int, float)) else "—"
        est = report.estimated_generation_time or "—"
        overall = report.overall_state or "NOT_READY"
        state_cls = _readiness_state_class(overall)
        empty_note = ""
        if overall == "NOT_READY" and not missing and not warnings:
            empty_note = (
                '<p class="mc-muted">No usable readiness evidence yet — '
                "components will appear as sources become available.</p>"
            )
        return (
            '<section class="mc-panel" id="executive-brief-readiness" '
            'aria-label="Executive Brief Readiness" '
            'data-phase="176J" data-advisory-only="true" '
            f'data-overall-state="{escape(overall)}">'
            "<h2>Executive Brief Readiness</h2>"
            '<p class="mc-muted">Advisory readiness layer only — no trading or execution impact. '
            "Computed from the current Mission Control snapshot (no polling loop).</p>"
            f"{empty_note}"
            "<table>"
            f"<tr><th>Overall State</th><td>"
            f'<em class="mc-status {state_cls}">{escape(overall)}</em></td></tr>'
            f"<tr><th>Score</th><td>{escape(score_txt)}</td></tr>"
            f"<tr><th>Missing Components</th><td>{escape(missing_txt)}</td></tr>"
            f"<tr><th>Warnings</th><td>{escape(warnings_txt)}</td></tr>"
            f"<tr><th>Estimated Generation Time</th><td>{escape(est)}</td></tr>"
            "</table>"
            '<p class="mc-muted"><a href="/mission-control/reports/viewer?source=reports_center&amp;report_code=daily_executive_brief">'
            "Open Daily Executive Brief</a></p>"
            "</section>"
        )
    except Exception as exc:  # noqa: BLE001 — never fail Executive Overview for readiness
        return (
            '<section class="mc-panel" id="executive-brief-readiness" '
            'aria-label="Executive Brief Readiness" '
            'data-phase="176J" data-advisory-only="true" data-overall-state="NOT_READY">'
            "<h2>Executive Brief Readiness</h2>"
            '<p class="mc-muted">Advisory readiness temporarily unavailable. '
            "Existing Executive Overview cards remain active.</p>"
            "<table>"
            '<tr><th>Overall State</th><td>'
            '<em class="mc-status bad">NOT_READY</em></td></tr>'
            "<tr><th>Score</th><td>—</td></tr>"
            "<tr><th>Missing Components</th><td>Unavailable</td></tr>"
            "<tr><th>Warnings</th><td>"
            f"{escape(type(exc).__name__)} during local evaluation</td></tr>"
            "<tr><th>Estimated Generation Time</th><td>—</td></tr>"
            "</table>"
            '<p class="mc-muted"><a href="/mission-control/reports/viewer?source=reports_center&amp;report_code=daily_executive_brief">'
            "Open Daily Executive Brief</a></p>"
            "</section>"
        )


def _financial_reporting_card(state: dict) -> str:
    """Phase 177/178 — consolidated Canonical + Executive Financial Reporting cards."""
    try:
        service = ExecutiveFinancialReportingService()
        package = service.generate_from_state(state)
        summary = package.get("financial_summary") if isinstance(package.get("financial_summary"), dict) else {}
        period = summary.get("reporting_period") if isinstance(summary.get("reporting_period"), dict) else {}
        period_label = period.get("label")
        ready_state = str(summary.get("reporting_readiness") or "NOT_READY")
        traffic = str(summary.get("profitability_traffic_light") or "NOT_AVAILABLE")
        ready_cls = _readiness_state_class(ready_state)
        traffic_cls = _readiness_state_class(traffic)
        generated = summary.get("generated_at") or package.get("generated_at") or "—"

        def _disp(value: object) -> str:
            if value is None:
                return "—"
            text = str(value)
            if text.strip().upper() in {"NONE", "NULL", "UNDEFINED", "NAN"}:
                return "—"
            return text

        actions = package.get("management_actions") if isinstance(package.get("management_actions"), list) else []
        top_action = ""
        if actions and isinstance(actions[0], dict):
            top_action = str(actions[0].get("action") or "")

        return (
            '<section class="mc-panel" id="canonical-financial-reporting" '
            'aria-label="Executive Financial Reporting" '
            'data-phase="178" data-advisory-only="true" '
            f'data-traffic-light="{escape(traffic)}" '
            f'data-readiness="{escape(ready_state)}">'
            "<h2>Executive Financial Summary</h2>"
            '<p class="mc-muted">Advisory management reporting (Phases 177/178) — not audited statutory statements. '
            "No trading or execution impact.</p>"
            "<table>"
            f"<tr><th>Reporting Period</th><td>{escape(_disp(period_label))}</td></tr>"
            f"<tr><th>Net Profit</th><td>{escape(_disp(summary.get('net_profit')))}</td></tr>"
            f"<tr><th>Target Profit</th><td>{escape(_disp(summary.get('target_profit')))}</td></tr>"
            f"<tr><th>Remaining Target</th><td>{escape(_disp(summary.get('remaining_profit_required')))}</td></tr>"
            f"<tr><th>Target Achieved %</th><td>{escape(_disp(summary.get('target_achieved_percentage')))}</td></tr>"
            f"<tr><th>Actual Daily Run Rate</th><td>{escape(_disp(summary.get('actual_daily_run_rate')))}</td></tr>"
            f"<tr><th>Required Daily Run Rate</th><td>{escape(_disp(summary.get('required_daily_run_rate')))}</td></tr>"
            f"<tr><th>Projected Period-End Profit</th><td>{escape(_disp(summary.get('projected_period_end_profit')))}</td></tr>"
            f"<tr><th>Target Variance</th><td>{escape(_disp(summary.get('projected_target_variance')))}</td></tr>"
            f"<tr><th>Profitability Traffic Light</th><td>"
            f'<em class="mc-status {traffic_cls}">{escape(traffic)}</em></td></tr>'
            f"<tr><th>Financial Reporting Readiness</th><td>"
            f'<em class="mc-status {ready_cls}">{escape(ready_state)}</em></td></tr>'
            f"<tr><th>Last Generated</th><td>{escape(_disp(generated))}</td></tr>"
            f"<tr><th>Top Management Action</th><td>{escape(_disp(top_action or '—'))}</td></tr>"
            "</table>"
            '<p class="mc-muted">Downloads via Reports Center: Executive Financial Summary, Income Statement, '
            "Balance Sheet, Cash-Flow Statement, Profitability Run-Rate Report.</p>"
            '<p class="mc-muted">'
            '<a href="/mission-control/reports/viewer?source=reports_center&amp;report_code=executive_financial_summary">Executive Financial Summary</a>'
            " · "
            '<a href="/mission-control/reports/viewer?source=reports_center&amp;report_code=canonical_income_statement">Income Statement</a>'
            " · "
            '<a href="/mission-control/reports/viewer?source=reports_center&amp;report_code=canonical_balance_sheet">Balance Sheet</a>'
            " · "
            '<a href="/mission-control/reports/viewer?source=reports_center&amp;report_code=canonical_cash_flow_statement">Cash-Flow Statement</a>'
            "</p>"
            "</section>"
        )
    except Exception as exc:  # noqa: BLE001 — never fail Executive Overview for reporting
        return (
            '<section class="mc-panel" id="canonical-financial-reporting" '
            'aria-label="Executive Financial Reporting" '
            'data-phase="178" data-advisory-only="true" '
            'data-traffic-light="NOT_AVAILABLE" data-readiness="NOT_READY">'
            "<h2>Executive Financial Summary</h2>"
            '<p class="mc-muted">Advisory financial reporting temporarily unavailable. '
            "Existing Executive Overview cards remain active.</p>"
            "<table>"
            "<tr><th>Reporting Period</th><td>—</td></tr>"
            "<tr><th>Net Profit</th><td>—</td></tr>"
            "<tr><th>Target Profit</th><td>—</td></tr>"
            "<tr><th>Remaining Target</th><td>—</td></tr>"
            "<tr><th>Target Achieved %</th><td>—</td></tr>"
            "<tr><th>Actual Daily Run Rate</th><td>—</td></tr>"
            "<tr><th>Required Daily Run Rate</th><td>—</td></tr>"
            "<tr><th>Projected Period-End Profit</th><td>—</td></tr>"
            "<tr><th>Target Variance</th><td>—</td></tr>"
            '<tr><th>Profitability Traffic Light</th><td>'
            '<em class="mc-status neutral">NOT_AVAILABLE</em></td></tr>'
            '<tr><th>Financial Reporting Readiness</th><td>'
            '<em class="mc-status bad">NOT_READY</em></td></tr>'
            "<tr><th>Last Generated</th><td>—</td></tr>"
            "<tr><th>Top Management Action</th><td>—</td></tr>"
            "</table>"
            f'<p class="mc-muted">{escape(type(exc).__name__)} during local evaluation</p>'
            '<p class="mc-muted"><a href="/mission-control/reports/viewer?source=reports_center&amp;report_code=executive_financial_summary">'
            "Open Executive Financial Summary</a></p>"
            "</section>"
        )


def _cockpit_status(value: object) -> str:
    text = str(value or "").strip().upper()
    if text in {"UNAVAILABLE", "DATA UNAVAILABLE", "SOURCE_UNAVAILABLE", "NOT_AVAILABLE"}:
        return "unavailable"
    return "neutral"


def _cockpit_holdings_rows(portfolio: dict) -> object:
    holdings = portfolio.get("holdings")
    if holdings in (None, "", "UNAVAILABLE", "DATA UNAVAILABLE"):
        return {"status": "UNAVAILABLE", "note": "No independent position evidence."}
    if isinstance(holdings, list):
        return holdings
    return {"status": "UNAVAILABLE", "note": "No independent position evidence."}


def _session_pnl_by_instrument_rows(portfolio: dict) -> dict:
    value = portfolio.get("session_pnl_by_instrument")
    if value in (None, "", "UNAVAILABLE", "DATA UNAVAILABLE") or value == []:
        return {
            "status": "UNAVAILABLE",
            "note": "Per-instrument P&L is unavailable. Asset-class P&L is not relabeled as instrument-level P&L.",
        }
    return {"status": "AVAILABLE", "rows": value}


def render(state: dict) -> str:
    platform = section(state, "platform")
    runtime = section(state, "runtime")
    portfolio = section(state, "portfolio")
    risk = section(state, "risk")
    market = section(state, "market_intelligence")
    alerts = section(state, "alerts")
    certification = section(state, "certification")
    freshness = section(state, "data_freshness")
    kpis = section(state, "executive_kpis")
    timeline = section(state, "operations_timeline")
    institutional = section(state, "institutional_executive_dashboard")
    reporting = section(state, "institutional_reporting")
    balance_summary = section(state, "broker_balance_summary")
    safety = section(state, "safety")
    operating = portfolio.get("operating_context") if isinstance(portfolio.get("operating_context"), dict) else {}
    liquidity = portfolio.get("liquidity_margin") if isinstance(portfolio.get("liquidity_margin"), dict) else {}
    maturity = portfolio.get("maturity_expiry") if isinstance(portfolio.get("maturity_expiry"), dict) else {}
    from backend.product_honesty import eis_dashboard_honesty

    honesty = eis_dashboard_honesty()
    return (
        page_header("Executive Overview", "Enterprise-level platform, runtime, capital, risk, readiness, and alert posture.")
        + warning_banner(honesty["customer_banner"], status="warn")
        + warning_banner(
            "RUNTIME OFFLINE - current runtime evidence is unavailable."
            if platform.get("runtime_offline")
            else "Runtime evidence is sourced from the canonical runtime snapshot.",
            status="bad" if platform.get("runtime_offline") else "good",
        )
        + warning_banner(state.get("mock_data_label", "RUNTIME DATA"), status="warn" if state.get("mock_data") else "good")
        + warning_banner(
            "Advisory / read-only cockpit. Execution allowed: false. Live trading blocked. Broker execution unarmed.",
            status="warn",
        )
        + metric_grid(
            (
                ("Cash", portfolio.get("cash"), _cockpit_status(portfolio.get("cash"))),
                ("Available / Free", portfolio.get("available_free"), _cockpit_status(portfolio.get("available_free"))),
                ("Portfolio Value", portfolio.get("portfolio_value"), _cockpit_status(portfolio.get("portfolio_value"))),
                ("Session P&L", portfolio.get("session_pnl"), _cockpit_status(portfolio.get("session_pnl"))),
                ("Realized P&L", portfolio.get("realized_pnl"), _cockpit_status(portfolio.get("realized_pnl"))),
                ("Unrealized P&L", portfolio.get("unrealized_pnl"), _cockpit_status(portfolio.get("unrealized_pnl"))),
                ("Open Positions", portfolio.get("open_positions"), _cockpit_status(portfolio.get("open_positions"))),
                ("Execution Status", portfolio.get("execution_status"), _cockpit_status(portfolio.get("execution_status"))),
            )
        )
        + split_panels(
            detail_table("Session P&L by Instrument", _session_pnl_by_instrument_rows(portfolio)),
            detail_table("Current Holdings / Positions", _cockpit_holdings_rows(portfolio)),
            detail_table("Liquidity / Margin", {
                "cash": liquidity.get("cash", portfolio.get("cash")),
                "available_free": liquidity.get("available_free", portfolio.get("available_free")),
                "buying_power": liquidity.get("buying_power", portfolio.get("buying_power")),
                "margin_used": liquidity.get("margin_used", "UNAVAILABLE"),
                "available_margin": liquidity.get("available_margin", "UNAVAILABLE"),
                "reserved_balance": "UNAVAILABLE",
                "source": liquidity.get("source", portfolio.get("source", "UNAVAILABLE")),
            }),
            detail_table("Maturity / Expiry Profile", {
                "status": maturity.get("status", "UNAVAILABLE"),
                "profile": maturity.get("profile", "UNAVAILABLE"),
                "next_maturity": maturity.get("next_maturity", "UNAVAILABLE"),
                "source": maturity.get("source", "UNAVAILABLE"),
                "note": "Maturity fields are shown only when launcher/runtime evidence exists.",
            }),
            detail_table("Operating Context", {
                "runtime_mode": operating.get("runtime_mode", platform.get("runtime_mode")),
                "advisory_only": operating.get("advisory_only", True),
                "read_only": operating.get("read_only", True),
                "execution_allowed": operating.get("execution_allowed", safety.get("execution_allowed", False)),
                "live_trading_blocked": operating.get("live_trading_blocked", safety.get("live_trading_blocked", True)),
                "broker_execution_armed": operating.get("broker_execution_armed", safety.get("broker_execution_armed", False)),
                "risk_state": risk.get("overall_risk_state", "UNAVAILABLE"),
                "safety_status": safety.get("safety_status", "UNAVAILABLE"),
                "source": operating.get("source", portfolio.get("source", "UNAVAILABLE")),
            }),
        )
        + _executive_brief_readiness_card(state)
        + _financial_reporting_card(state)
        + _executive_decision_intelligence_card(state)
        + metric_grid(
            (
                ("Platform Status", platform.get("platform_status"), platform.get("platform_status")),
                ("Runtime Health", platform.get("runtime_health"), platform.get("runtime_health")),
                ("Runtime Mode", platform.get("runtime_mode"), platform.get("runtime_mode")),
                ("Engine Mode", platform.get("engine_mode"), "neutral"),
                ("Cycle", platform.get("cycle"), "neutral"),
                ("Heartbeat", platform.get("heartbeat"), runtime.get("heartbeat_status", "neutral")),
                ("Broker Health", platform.get("broker_health"), platform.get("broker_health")),
                ("Portfolio Equity", portfolio.get("equity"), "neutral"),
                ("Cash / Buying Power", portfolio.get("buying_power"), "neutral"),
                ("Risk Status", risk.get("overall_risk_state"), risk.get("overall_risk_state")),
                ("Market Regime", market.get("market_regime"), market.get("market_regime")),
                ("Active Alerts", alerts.get("count"), "good" if alerts.get("count") == 0 else "warn"),
                ("RC1 Certification", certification.get("rc1_platform_certification"), certification.get("rc1_platform_certification")),
                ("Last Runtime Heartbeat", freshness.get("last_runtime_heartbeat"), "neutral"),
            )
        )
        + split_panels(
            detail_table("Canonical Account Balance", balance_summary),
            detail_table("Executive KPI Board", {
                "uptime": kpis.get("uptime"),
                "runtime_health": kpis.get("runtime_health"),
                "broker_health": kpis.get("broker_health"),
                "portfolio_health": kpis.get("portfolio_health"),
                "risk_health": kpis.get("risk_health"),
                "market_health": kpis.get("market_health"),
                "alert_count": kpis.get("alert_count"),
                "trade_quality": kpis.get("trade_quality"),
                "system_readiness": kpis.get("system_readiness"),
                "rc1_readiness": kpis.get("rc1_readiness"),
                "source": kpis.get("source"),
                "state_hash": kpis.get("state_hash"),
            }),
            detail_table("Institutional Dashboard", {
                "platform_health": institutional.get("platform_health"),
                "investment_health": institutional.get("investment_health"),
                "risk_health": institutional.get("risk_health"),
                "broker_health": institutional.get("broker_health"),
                "runtime_health": institutional.get("runtime_health"),
                "portfolio_health": institutional.get("portfolio_health"),
                "capital_health": institutional.get("capital_health"),
                "links": institutional.get("links"),
                "state_hash": institutional.get("state_hash"),
            }),
            detail_table("Institutional Reports", reporting.get("summaries", [])),
            detail_table("Operations Timeline", timeline.get("events", [])[:8]),
            detail_table("Capital And PnL", {
                "cash": portfolio.get("cash"),
                "buying_power": portfolio.get("buying_power"),
                "realized_pnl": section(state, "portfolio").get("realized_pnl", "UNAVAILABLE"),
                "unrealized_pnl": section(state, "portfolio").get("unrealized_pnl", "UNAVAILABLE"),
                "net_pnl": section(state, "portfolio").get("net_pnl", "UNAVAILABLE"),
                "open_positions": len(portfolio.get("positions", []) or []),
                "open_position_count": portfolio.get("open_positions"),
                "capital_utilization": portfolio.get("capital_deployed"),
                "drawdown": portfolio.get("drawdown"),
            }),
            detail_table("Readiness", {
                "ready_for_controlled_rc1_runtime": certification.get("ready_for_controlled_rc1_runtime"),
                "ready_for_live_trading": certification.get("ready_for_live_trading"),
                "data_freshness": freshness.get("generated_at"),
                "overall_freshness": freshness.get("overall_freshness"),
                "last_runtime_heartbeat": freshness.get("last_runtime_heartbeat"),
                "live_trading_blocked": state.get("safety", {}).get("live_trading_blocked"),
            }),
        )
    )
