from __future__ import annotations

from fastapi.testclient import TestClient

from dashboard.mobile import mobile_app
from dashboard.runtime.api_bridge import create_app
from dashboard.runtime.dashboard_hydration_coordinator import DashboardHydrationCoordinator
from dashboard.runtime.frontend_contract import build_frontend_payload
from dashboard.runtime.runtime_smoke_test import build_smoke_payloads
from dashboard.web.web_app import _trade_summary_page


TRADER = {"user_id": "00017", "display_name": "CSS Trader", "role": "TRADER"}
SESSION = {"created": 1.0}


def _state():
    return DashboardHydrationCoordinator().hydrate(**build_smoke_payloads())


def test_phase_140b_trade_summary_contract_uses_canonical_fields() -> None:
    summary = build_frontend_payload(_state())["sections"]["trade_summary"]

    assert summary["mode"] == "paper"
    assert summary["broker"] == "DEMO"
    assert summary["engine_mode"] == "SAFE"
    assert summary["account_balance"] == 10000.0
    assert summary["equity"] == 10250.0
    assert summary["open_positions"] == 2
    assert summary["realized_pnl"] == 0.0
    assert summary["unrealized_pnl"] == 27.5
    assert summary["execution_status"] == "READY"
    assert summary["execution_allowed"] is False


def test_phase_140b_missing_values_render_data_unavailable() -> None:
    summary = build_frontend_payload({})["sections"]["trade_summary"]

    assert summary["broker"] == "DATA UNAVAILABLE"
    assert summary["account_balance"] == "DATA UNAVAILABLE"
    assert summary["equity"] == "DATA UNAVAILABLE"
    assert summary["execution_allowed"] is False


def test_phase_140b_read_only_api_route_returns_trade_summary() -> None:
    client = TestClient(create_app(_state))
    response = client.get("/api/v1/trade-summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["section"] == "trade_summary"
    assert payload["data"]["broker"] == "DEMO"
    assert payload["data"]["execution_allowed"] is False


def test_phase_140b_desktop_and_mobile_trade_summary_pages_render_compact_fields() -> None:
    desktop = _trade_summary_page()
    mobile = mobile_app._trade_summary_page(TRADER, SESSION)

    for expected in ["Date / Time", "Mode", "Broker", "Engine Mode", "Account Balance", "Execution Status"]:
        assert expected in desktop
        assert expected in mobile
    assert "No order controls" in desktop
    assert "Compact Trade Summary" in mobile
