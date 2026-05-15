from __future__ import annotations

from dashboard.runtime.api_bridge import get_frontend_payload
from dashboard.web.web_app import (
    _broker_page,
    _dashboard_page,
    _execution_page,
    _market_opportunities_page,
    _micro_live_manual_pilot_checklist_page,
    _micro_live_pilot_readiness_page,
    _positions_page,
    _runtime_event_persistence_checklist_print_page,
    _runtime_event_persistence_sim_page,
    _runtime_events_page,
    _replay_page,
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
        "/micro-live-manual-pilot-checklist",
        "/micro-live-pilot-readiness",
        "/positions",
        "/replay",
        "/runtime-events",
        "/runtime-event-persistence-sim",
        "/runtime-event-persistence-checklist-print",
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
        "/api/v1/alerts",
        "/api/v1/coinbase-micro-live-dry-run-probe",
        "/api/v1/micro-live-broker-readiness-confirmation",
        "/api/v1/micro-live-manual-pilot-checklist",
        "/api/v1/micro-live-operator-approval-gate",
        "/api/v1/micro-live-pre-pilot-go-no-go",
        "/api/v1/micro-live-pilot-readiness",
        "/api/v1/micro-live-pilot-order-intent",
        "/api/v1/runtime-events",
        "/api/v1/runtime-event-persistence-checklist",
        "/api/v1/runtime-event-persistence-checklist-export",
        "/api/v1/runtime-event-persistence-policy",
        "/api/v1/runtime-event-persistence-report",
        "/api/v1/runtime-event-persistence-sim",
        "/api/v1/runtime-event-persistence-scenarios",
        "/api/v1/deployment-profiles",
        "/api/v1/trade-lifecycle-replay",
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
        'href="/micro-live-manual-pilot-checklist"',
        'href="/micro-live-pilot-readiness"',
        'href="/positions"',
        'href="/risk-governance"',
        'href="/replay"',
        'href="/runtime-events"',
        'href="/runtime-event-persistence-sim"',
        'href="/runtime-event-persistence-checklist-print"',
        "/api/v1/frontend-state",
        "/ws/v1/dashboard-state",
    ]
    for expected in expected_markup:
        if expected not in markup:
            raise AssertionError(f"Web dashboard markup missing: {expected}")

    persistence_sim_markup = _runtime_event_persistence_sim_page()
    expected_persistence_sim_markup = [
        "CSS Runtime Event Persistence Simulator",
        "Persistence Simulation Review",
        "Persistence Simulation Results",
        "Rejection Reasons",
        "Subsystem Breakdown",
        "Simulation Warnings",
        "Backend Recommendation",
        "Storage Backend Comparison",
        "Governance Blockers",
        "Persistence Dry-Run Report",
        "Report Safety Assertions",
        "Approval Requirements",
        "Operator Approval Checklist",
        "Checklist Failed Checks",
        "Checklist Warnings",
        "SIMULATION ONLY - persistence remains disabled",
        "No persistence simulation events match the current view",
        "/api/v1/runtime-event-persistence-checklist",
        "/api/v1/runtime-event-persistence-report",
        "/api/v1/runtime-event-persistence-sim",
        "/api/v1/runtime-event-persistence-scenarios",
    ]
    for expected in expected_persistence_sim_markup:
        if expected not in persistence_sim_markup:
            raise AssertionError(f"Web persistence simulator markup missing: {expected}")

    checklist_print_markup = _runtime_event_persistence_checklist_print_page()
    expected_checklist_print_markup = [
        "CSS Persistence Checklist Print View",
        "Persistence Checklist Print View",
        "Read-only export view",
        "No approval action",
        "Persistence remains disabled",
        "Required Checks",
        "Passed Checks",
        "Failed Checks",
        "Blocking Items",
        "Warnings",
        "/api/v1/runtime-event-persistence-checklist-export",
    ]
    for expected in expected_checklist_print_markup:
        if expected not in checklist_print_markup:
            raise AssertionError(f"Web checklist print markup missing: {expected}")

    pilot_markup = _micro_live_pilot_readiness_page()
    expected_pilot_markup = [
        "CSS Micro-Live Pilot Readiness",
        "Controlled Micro-Live Pilot Readiness",
        "Readiness review only",
        "No live order action",
        "No approval grant",
        "No unrestricted live trading",
        "No order will be placed from this page",
        "No order was submitted",
        "Manual approval still required; no trading is armed",
        "No broker state was modified",
        "No trading is armed from this page",
        "Approved Pilot Constraints",
        "Live Restrictions",
        "Order Intent Evidence",
        "Coinbase Dry-Run Probe Evidence",
        "Probe Blockers / Warnings",
        "Operator Approval Gate",
        "Kill-Switch Verification Evidence",
        "Approval Gate Blockers / Warnings",
        "Broker Readiness Confirmation",
        "Broker Confirmation Checks",
        "Broker Confirmation Blockers / Warnings",
        "Final Pre-Pilot Go/No-Go",
        "Go/No-Go Checks",
        "Go/No-Go Blockers / Warnings",
        "Required Approvals",
        "Coinbase Advanced",
        "BTC-USD",
        "CAD $15",
        "Persistence remains disabled",
        "/api/v1/micro-live-pilot-readiness",
        "/api/v1/micro-live-pilot-order-intent",
        "/api/v1/coinbase-micro-live-dry-run-probe",
        "/api/v1/micro-live-operator-approval-gate",
        "/api/v1/micro-live-broker-readiness-confirmation",
        "/api/v1/micro-live-pre-pilot-go-no-go",
    ]
    for expected in expected_pilot_markup:
        if expected not in pilot_markup:
            raise AssertionError(f"Web micro-live pilot markup missing: {expected}")

    manual_checklist_markup = _micro_live_manual_pilot_checklist_page()
    expected_manual_checklist_markup = [
        "CSS Manual Micro-Live Pilot Checklist",
        "Manual Micro-Live Pilot Checklist",
        "Checklist/export only",
        "No approval grant",
        "No live order action",
        "No trading is armed by this checklist",
        "Pilot Scope",
        "Required Items",
        "Completed Items",
        "Missing Items",
        "Blockers / Warnings",
        "Evidence Chain Summary",
        "Safety Disclaimer",
        "Coinbase Advanced",
        "BTC-USD",
        "CAD $15",
        "/api/v1/micro-live-manual-pilot-checklist",
    ]
    for expected in expected_manual_checklist_markup:
        if expected not in manual_checklist_markup:
            raise AssertionError(
                f"Web manual pilot checklist markup missing: {expected}"
            )

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

    replay_markup = _replay_page()
    expected_replay_markup = [
        "CSS Lifecycle Replay Viewer",
        "Lifecycle Replay Viewer",
        "Lifecycle Replay Table",
        "Event Mix",
        "Replay Health",
        "Total Events",
        "Realized PnL Handoffs",
        "Defensive Reductions",
        "Exits Booked",
        "/api/v1/trade-lifecycle-replay",
    ]
    for expected in expected_replay_markup:
        if expected not in replay_markup:
            raise AssertionError(f"Web replay markup missing: {expected}")

    runtime_events_markup = _runtime_events_page()
    expected_runtime_events_markup = [
        "CSS Runtime Events",
        "Runtime Event Bus",
        "Runtime Event Table",
        "Subsystem Mix",
        "Severity Mix",
        "No runtime events match the current view",
        "/api/v1/runtime-events",
    ]
    for expected in expected_runtime_events_markup:
        if expected not in runtime_events_markup:
            raise AssertionError(f"Web runtime events markup missing: {expected}")

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
