from __future__ import annotations

from dashboard.runtime.api_bridge import get_frontend_payload
from dashboard.web.web_app import (
    _dashboard_page,
    create_app,
    demo_dashboard_state_provider,
)


def main() -> int:
    app = create_app()
    routes = {getattr(route, "path", "") for route in app.routes}
    required_routes = {
        "/",
        "/dashboard",
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
        "/api/v1/frontend-state",
        "/ws/v1/dashboard-state",
    ]
    for expected in expected_markup:
        if expected not in markup:
            raise AssertionError(f"Web dashboard markup missing: {expected}")

    payload = get_frontend_payload(demo_dashboard_state_provider)
    sections = payload.get("sections", {})
    if sections.get("account_summary", {}).get("broker") != "DEMO":
        raise AssertionError("Web dashboard provider must expose demo account payload")
    if sections.get("positions", {}).get("total") != 2:
        raise AssertionError("Web dashboard provider must expose demo positions")
    if sections.get("risk", {}).get("risk_state") != "NORMAL":
        raise AssertionError("Web dashboard provider must expose demo risk state")
    if sections.get("execution", {}).get("execution_state") != "READY":
        raise AssertionError("Web dashboard provider must expose demo execution state")

    print("CSS institutional web dashboard smoke test PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
