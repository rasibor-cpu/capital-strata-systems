from __future__ import annotations

from dashboard.runtime.api_bridge import get_frontend_payload
from dashboard.web.web_app import (
    _billing_page,
    _broker_page,
    _dashboard_page,
    _execution_page,
    _market_opportunities_page,
    _positions_page,
    _risk_governance_page,
    _trial_contract_page,
    _commercialization_operations_page,
    create_app,
    demo_dashboard_state_provider,
)


def main() -> int:
    app = create_app()
    routes = {getattr(route, "path", "") for route in app.routes}
    required_routes = {
        "/",
        "/billing",
        "/broker",
        "/dashboard",
        "/execution",
        "/market-opportunities",
        "/positions",
        "/risk-governance",
        "/trial-contract",
        "/commercialization-operations",
        "/health",
        "/api/v1/dashboard-state",
        "/api/v1/frontend-state",
        "/api/v1/account-summary",
        "/api/v1/positions",
        "/api/v1/risk",
        "/api/v1/governance",
        "/api/v1/opportunities",
        "/api/v1/broker",
        "/api/v1/client-earnings-summary",
        "/api/v1/client-earnings-history",
        "/api/v1/customer-profitability-summary",
        "/api/v1/advice-profitability-history",
        "/api/v1/commercial-trial/agreement",
        "/api/v1/commercial-trial/enroll",
        "/api/v1/commercial-trial/cancel",
        "/api/v1/commercial-trial/status",
        "/api/v1/production-charging/readiness",
        "/api/v1/payment-collection/preflight",
        "/api/v1/customer-notifications/preflight",
        "/api/v1/launch-dossier/export",
        "/api/v1/commercialization-operations/status",
        "/api/v1/commercialization-release/readiness",
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

    billing_markup = _billing_page()
    expected_billing_markup = [
        "CSS Client Earnings &amp; Charges",
        "CSS-Attributable New Gain",
        "Platform access reference",
        "Final CSS performance charge",
        "Advice Profitability History",
        "Independent / Customer-Directed P&amp;L",
        "Independent Platform Charge",
        "Gross Customer Profit",
        "Total CSS Charges",
        "Customer Net After All CSS Charges",
        "customer result → loss recovery → fresh gain → CSS fee → customer retained",
        "/api/v1/client-earnings-summary",
        "/api/v1/customer-profitability-summary",
        "/api/v1/advice-profitability-history",
    ]
    for expected in expected_billing_markup:
        if expected not in billing_markup:
            raise AssertionError(f"Web billing markup missing: {expected}")

    forbidden_billing_language = [
        "higher of your platform minimum or your performance fee",
        "PLATFORM MINIMUM APPLIED",
    ]
    for forbidden in forbidden_billing_language:
        if forbidden in billing_markup:
            raise AssertionError(
                f"Stale commercialization language remains in billing UI: {forbidden}"
            )

    trial_contract_markup = _trial_contract_page()
    expected_trial_contract_markup = [
        "CSS Trial &amp; Customer Agreement",
        "Commercial Terms Presented to Customer",
        "Affirmative Acceptance",
        "Both confirmations are mandatory",
        "I have reviewed and accept the exact agreement version and pricing shown above.",
        "paid CSS service begins automatically if I do not cancel before the exact trial expiry",
        "No payment execution",
        "/api/v1/commercial-trial/agreement",
        "/api/v1/commercial-trial/enroll",
        "/api/v1/commercial-trial/cancel",
        "/api/v1/commercial-trial/status",
    ]
    for expected in expected_trial_contract_markup:
        if expected not in trial_contract_markup:
            raise AssertionError(
                f"Web trial contract markup missing: {expected}"
            )

    operations_markup = _commercialization_operations_page()
    expected_operations_markup = [
        "CSS Commercialization Operations",
        "Commercialization Operations",
        "Read-only launch control",
        "Release Blockers",
        "UAT Coverage",
        "Launch Evidence Dossier",
        "Jurisdiction Service Modes",
        "Customer Notification Intents",
        "Payment Provider Ready",
        "No payment execution",
        "No trading authority",
        "/api/v1/commercialization-operations/status",
    ]
    for expected in expected_operations_markup:
        if expected not in operations_markup:
            raise AssertionError(
                f"Commercialization operations markup missing: {expected}"
            )

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
