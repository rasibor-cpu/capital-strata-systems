from __future__ import annotations

from dashboard.mission_control.pages._components import detail_table, metric_grid, page_header, section, split_panels, warning_banner


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
    return (
        page_header("Executive Overview", "Enterprise-level platform, runtime, capital, risk, readiness, and alert posture.")
        + warning_banner(
            "RUNTIME OFFLINE - current runtime evidence is unavailable."
            if platform.get("runtime_offline")
            else "Runtime evidence is sourced from the canonical runtime snapshot.",
            status="bad" if platform.get("runtime_offline") else "good",
        )
        + warning_banner(state.get("mock_data_label", "RUNTIME DATA"), status="warn" if state.get("mock_data") else "good")
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
