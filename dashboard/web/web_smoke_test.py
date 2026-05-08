from __future__ import annotations

from dashboard.runtime.api_bridge import get_frontend_payload
from dashboard.web.web_app import (
    _broker_page,
    _dashboard_page,
    _execution_page,
    _market_opportunities_page,
    _positions_page,
    _risk_governance_page,
    create_app,
    demo_dashboard_state_provider,
)


def main() -> int:
    app = create_app()
    routes = {getattr(route, "path", "") for route in app.routes}
    required_routes = {
        "/",
        "/broker",
        "/dashboard",
        "/execution",
        "/market-opportunities",
        "/positions",
        "/risk-governance",
        "/health",
        "/api/v1/dashboard-state",
        "/api/v1/frontend-state",
        "/api/v1/account-summary",
        "/api/v1/positions",
        "/api/v1/risk",
        "/api/v1/governance",
        "/api/v1/opportunities",
        "/api/v1/broker",
        "/ws/v1/dashboard-state",
    }
    missing = required_routes - routes
    if missing:
        raise AssertionError(f"Missing web dashboard routes: {sorted(missing)}")

    markup = _dashboard_page()
    expected_markup = [
        "CSS Institutional Web Dashboard",
        "Institutional Web Dashboard",
        "Account Overview",
        "Live Positions",
        "Risk Control Center",
        "Governance Center",
        "Market Regime Panel",
        "Execution Center",
        "Broker Control Panel",
        "Opportunity Monitor",
        'href="/broker"',
        'href="/execution"',
        'href="/market-opportunities"',
        'href="/positions"',
        'href="/risk-governance"',
        "/api/v1/frontend-state",
        "/ws/v1/dashboard-state",
    ]
    for expected in expected_markup:
        if expected not in markup:
            raise AssertionError(f"Web dashboard markup missing: {expected}")

    positions_markup = _positions_page()
    expected_positions_markup = [
        "CSS Professional Positions",
        "Professional Positions",
        "Position Inventory",
        "Asset Allocation",
        "Active Symbols",
        "DashboardState positions contract",
        "/api/v1/frontend-state",
    ]
    for expected in expected_positions_markup:
        if expected not in positions_markup:
            raise AssertionError(f"Web positions markup missing: {expected}")

    execution_markup = _execution_page()
    expected_execution_markup = [
        "CSS Execution History",
        "Execution / Trade History",
        "Trade / Execution History",
        "Cost Breakdown",
        "Last Event",
        "DashboardState execution contract",
        "/api/v1/frontend-state",
    ]
    for expected in expected_execution_markup:
        if expected not in execution_markup:
            raise AssertionError(f"Web execution markup missing: {expected}")

    risk_governance_markup = _risk_governance_page()
    expected_risk_governance_markup = [
        "CSS Risk & Governance Center",
        "Risk & Governance Center",
        "Risk Control Center",
        "Governance Authority",
        "Risk Limit Breaches",
        "DashboardState risk contract",
        "/api/v1/frontend-state",
    ]
    for expected in expected_risk_governance_markup:
        if expected not in risk_governance_markup:
            raise AssertionError(f"Web risk/governance markup missing: {expected}")

    market_opportunities_markup = _market_opportunities_page()
    expected_market_opportunities_markup = [
        "CSS Market & Opportunity Center",
        "Market & Opportunity Center",
        "Market Regime Panel",
        "Opportunity Monitor",
        "DashboardState market contract",
        "/api/v1/frontend-state",
    ]
    for expected in expected_market_opportunities_markup:
        if expected not in market_opportunities_markup:
            raise AssertionError(f"Web market/opportunity markup missing: {expected}")

    broker_markup = _broker_page()
    expected_broker_markup = [
        "CSS Broker Control Center",
        "Broker Control Center",
        "Broker Readiness",
        "Mode Resolution",
        "Safety Boundary",
        "Broker secrets are never displayed",
        "API Health",
        "Reconnect State",
        "Supported Assets",
        "Broker Latency",
        "Account Readiness",
        "WARNING: Broker credentials missing. Trade execution disabled.",
        "/api/v1/frontend-state",
    ]
    for expected in expected_broker_markup:
        if expected not in broker_markup:
            raise AssertionError(f"Web broker markup missing: {expected}")

    payload = get_frontend_payload(demo_dashboard_state_provider)
    sections = payload.get("sections", {})
    if sections.get("account_summary", {}).get("broker") != "DEMO":
        raise AssertionError("Web dashboard provider must expose demo account payload")
    if sections.get("positions", {}).get("total") != 2:
        raise AssertionError("Web dashboard provider must expose demo positions")
    position_items = sections.get("positions", {}).get("items", [])
    if len(position_items) != 2:
        raise AssertionError("Web positions contract must expose detailed rows")
    if position_items[0].get("symbol") != "BTC-USD":
        raise AssertionError("Web positions contract must preserve position symbols")
    if sections.get("risk", {}).get("risk_state") != "NORMAL":
        raise AssertionError("Web dashboard provider must expose demo risk state")
    if sections.get("risk", {}).get("gate_status") != "OPEN":
        raise AssertionError("Web risk center must expose risk gate status")
    if sections.get("governance", {}).get("governance_enabled") is not True:
        raise AssertionError("Web governance center must expose governance authority")
    if sections.get("market", {}).get("regime_state") != "RISK_ON":
        raise AssertionError("Web market center must expose market regime")
    if sections.get("opportunities", {}).get("count") != 2:
        raise AssertionError("Web opportunity center must expose monitor rows")
    if sections.get("broker", {}).get("selected_broker") != "DEMO":
        raise AssertionError("Web broker center must expose selected broker")
    if sections.get("broker", {}).get("broker_mode") != "paper":
        raise AssertionError("Web broker center must expose broker mode")
    if sections.get("execution", {}).get("execution_state") != "READY":
        raise AssertionError("Web dashboard provider must expose demo execution state")
    recent_trades = sections.get("execution", {}).get("recent_trades", [])
    if len(recent_trades) != 2:
        raise AssertionError("Web execution contract must expose recent trades")
    if recent_trades[0].get("status") != "PAPER_TICKET_RECORDED":
        raise AssertionError("Web execution contract must preserve trade status")

    print("CSS institutional web dashboard smoke test PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
