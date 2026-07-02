from __future__ import annotations

from fastapi.testclient import TestClient

from dashboard.mobile import mobile_app
from dashboard.runtime.api_bridge import create_app
from dashboard.runtime.dashboard_hydration_coordinator import DashboardHydrationCoordinator
from dashboard.runtime.frontend_contract import build_frontend_payload
from dashboard.runtime.runtime_smoke_test import build_smoke_payloads
from dashboard.web.web_app import _session_command_centre_page


TRADER = {"user_id": "00017", "display_name": "CSS Trader", "role": "TRADER"}
SESSION = {"created": 1.0}


def _state():
    return DashboardHydrationCoordinator().hydrate(**build_smoke_payloads())


def test_phase_141_session_command_centre_contract_contains_required_sections() -> None:
    centre = build_frontend_payload(_state())["sections"]["session_command_centre"]

    for key in [
        "session_status",
        "account_summary",
        "trading_activity",
        "risk_dashboard",
        "opportunity_centre",
        "runtime_health",
        "intelligence_summary",
        "daily_executive_summary",
        "navigation_links",
        "intelligence_cards",
    ]:
        assert key in centre

    assert "trade_quality_score" in centre
    assert "capital_efficiency_score" in centre
    assert "engine_health_score" in centre
    assert "ai_market_narrative" in centre
    assert centre["execution_allowed"] is False


def test_phase_141_scores_and_ai_market_narrative_are_display_only() -> None:
    centre = build_frontend_payload(_state())["sections"]["session_command_centre"]

    assert 0 <= centre["trade_quality_score"] <= 100
    assert 0 <= centre["capital_efficiency_score"] <= 100
    assert 0 <= centre["engine_health_score"] <= 100
    assert "Display-only intelligence" in centre["ai_market_narrative"]
    assert len(centre["intelligence_cards"]) >= 4


def test_phase_141_read_only_api_route_returns_command_centre() -> None:
    client = TestClient(create_app(_state))
    response = client.get("/api/v1/session-command-centre")

    assert response.status_code == 200
    payload = response.json()
    assert payload["section"] == "session_command_centre"
    assert payload["data"]["execution_allowed"] is False
    assert payload["data"]["daily_executive_summary"]


def test_phase_141_desktop_and_mobile_command_centre_render_required_labels() -> None:
    desktop = _session_command_centre_page()
    mobile = mobile_app._session_command_centre_page(TRADER, SESSION)

    for expected in [
        "Session Command Centre",
        "Trade Quality Score",
        "Capital Efficiency Score",
        "Engine Health Score",
        "AI Market Narrative",
        "Daily Executive Summary",
        "Intelligence Cards",
        "Navigation Links",
    ]:
        assert expected in desktop
        assert expected in mobile
