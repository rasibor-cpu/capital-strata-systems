import pytest
import asyncio
from typing import Any

from dashboard.web import web_app
from dashboard.mobile import mobile_app
from dashboard.runtime.api_bridge import DashboardStateProvider
from dashboard.runtime.dashboard_state import DashboardState
from engine.risk.margin_snapshot import MarginSnapshot, MarginState
from engine.risk.oanda_margin_adapter import OandaMarginAdapter


class MockDashboardStateProvider:
    def __call__(self) -> DashboardState:
        state = DashboardState(session_id="test")
        state.last_scan_results["account_summary"] = {
            "broker": "OANDA",
            "account_mode": "SIMULATED"
        }
        return state

class UnavailableMockDashboardStateProvider:
    def __call__(self) -> DashboardState:
        state = DashboardState(session_id="test")
        state.last_scan_results["account_summary"] = {
            "broker": "UNKNOWN_BROKER",
            "account_mode": "SIMULATED"
        }
        return state


def test_web_margin_visibility_renders():
    html = web_app._margin_page()
    assert "Canonical Margin Visibility" in html
    assert "DATA UNAVAILABLE" in html


def test_web_margin_snapshot_api_returns_data(monkeypatch):
    app = web_app.create_app(MockDashboardStateProvider())
    margin_api = next(r.endpoint for r in app.routes if r.path == "/api/v1/margin-snapshot")
    
    def mock_get_snapshot(self):
        return MarginSnapshot(
            broker="OANDA",
            account_id="mock",
            timestamp="2026-06-17",
            equity=1000.0,
            cash=1000.0,
            buying_power=2000.0,
            maintenance_margin=100.0,
            initial_margin=200.0,
            margin_used=100.0,
            margin_available=900.0,
            margin_ratio=0.1,
            margin_state=MarginState.NORMAL
        )
    monkeypatch.setattr(OandaMarginAdapter, "get_margin_snapshot", mock_get_snapshot)
    
    data = asyncio.run(margin_api())
    assert data["ok"] is True
    assert data["broker"] == "OANDA"
    assert data["margin_state"] == "NORMAL"
    assert data["buying_power"] == 2000.0


def test_web_margin_snapshot_api_unavailable(monkeypatch):
    app = web_app.create_app(UnavailableMockDashboardStateProvider())
    margin_api = next(r.endpoint for r in app.routes if r.path == "/api/v1/margin-snapshot")
    
    data = asyncio.run(margin_api())
    assert data["ok"] is False
    assert data["status"] == "DATA_UNAVAILABLE"


def test_mobile_margin_visibility_renders():
    html = mobile_app._margin_page({"role": "VIEWER", "display_name": "Test"}, {})
    assert "Margin Visibility" in html
    assert "DATA UNAVAILABLE" in html


def test_mobile_margin_api_returns_data(monkeypatch):
    def mock_get_session(*args, **kwargs):
        return {"user_ctx": {"role": "VIEWER", "display_name": "Test"}}
        
    def mock_payload(*args, **kwargs):
        return {"broker_summary": {"selected_broker": "OANDA", "broker_mode": "SIMULATED"}}
    
    monkeypatch.setattr(mobile_app, "_get_session", mock_get_session)
    monkeypatch.setattr(mobile_app, "_mobile_dashboard_payload", mock_payload)
    
    def mock_get_snapshot(self):
        return MarginSnapshot(
            broker="OANDA",
            account_id="mock",
            timestamp="2026-06-17",
            equity=1000.0,
            cash=1000.0,
            buying_power=2000.0,
            maintenance_margin=100.0,
            initial_margin=200.0,
            margin_used=100.0,
            margin_available=900.0,
            margin_ratio=0.1,
            margin_state=MarginState.NORMAL
        )
    monkeypatch.setattr(OandaMarginAdapter, "get_margin_snapshot", mock_get_snapshot)
    
    margin_api = next(r.endpoint for r in mobile_app.app.routes if r.path == "/api/margin-snapshot")
    response = asyncio.run(margin_api(None))
    import json
    data = json.loads(response.body.decode('utf-8'))
    assert data["ok"] is True
    assert data["broker"] == "OANDA"
    assert data["margin_state"] == "NORMAL"


def test_mobile_margin_api_unavailable(monkeypatch):
    def mock_get_session(*args, **kwargs):
        return {"user_ctx": {"role": "VIEWER", "display_name": "Test"}}
        
    def mock_payload(*args, **kwargs):
        return {"broker_summary": {"selected_broker": "UNKNOWN"}}
    
    monkeypatch.setattr(mobile_app, "_get_session", mock_get_session)
    monkeypatch.setattr(mobile_app, "_mobile_dashboard_payload", mock_payload)
    
    margin_api = next(r.endpoint for r in mobile_app.app.routes if r.path == "/api/margin-snapshot")
    response = asyncio.run(margin_api(None))
    import json
    data = json.loads(response.body.decode('utf-8'))
    assert data["ok"] is False
    assert data["status"] == "DATA_UNAVAILABLE"
