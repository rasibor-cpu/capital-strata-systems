import pytest
from unittest.mock import patch, MagicMock

import os
import sys

os.environ["CSS_TEST_MODE"] = "1"
os.environ["OANDA_API_KEY"] = "mock_key"
os.environ["OANDA_ACCOUNT_ID"] = "mock_acc"
os.environ["OANDA_BASE_URL"] = "http://127.0.0.1:9999"
os.environ["OANDA_ENV"] = "practice"
os.environ["DATA_PROVIDER"] = "SIMULATED"

mock_auth = MagicMock()
mock_auth.await_login_ready_state.return_value = {
    "user_id": "test", 
    "role": "admin", 
    "display_name": "test", 
    "unit_code": "test", 
    "home_branch": "test"
}
sys.modules["dashboard.auth.css_sign_on"] = mock_auth
sys.modules["builtins"].input = lambda prompt: "1"

from backend.app.brokers.oanda_adapter import OandaAdapter


@pytest.fixture(scope="module")
def dashboard():
    import scripts.css_live_dashboard as db
    return db

@pytest.fixture(autouse=True)
def reset_state(dashboard):
    dashboard._CSS_SESSION_LOCK["locked"] = False
    dashboard._CSS_SESSION_LOCK["reason"] = None
    dashboard.oanda.health_state = "GREEN"
    dashboard.oanda.consecutive_failures = 0
    dashboard.oanda.margin_rejection_lock = False
    dashboard.RECONCILIATION_STATUS = "HEALTHY"
    dashboard.SELECTED_BROKER = "OANDA"
    dashboard.BROKER_EXECUTION_ARMED = True

def test_http_429_handling_recovery(dashboard):
    with patch("backend.app.brokers.oanda_adapter.requests.request") as mock_req:
        mock_req.side_effect = [
            MagicMock(status_code=429),
            MagicMock(status_code=200, json=lambda: {"test": "ok"})
        ]
        
        with patch("time.sleep") as mock_sleep:
            resp = dashboard.oanda._request_json("GET", "test")
            
            assert resp["ok"] is True
            assert dashboard.oanda.health_state == "GREEN"
            assert mock_req.call_count == 2
            mock_sleep.assert_called_once()

def test_retry_exhaustion_429(dashboard):
    with patch("backend.app.brokers.oanda_adapter.requests.request") as mock_req:
        mock_req.return_value = MagicMock(status_code=429)
        
        with patch("time.sleep"):
            resp = dashboard.oanda._request_json("GET", "test")
            
            assert resp["ok"] is False
            assert resp["error"] == "rate_limit_exhausted"
            assert dashboard.oanda.consecutive_failures == 1

def test_broker_red_state_escalation(dashboard):
    with patch("backend.app.brokers.oanda_adapter.requests.request") as mock_req:
        mock_req.return_value = MagicMock(status_code=500)
        
        with patch("time.sleep"):
            for _ in range(5):
                dashboard.oanda._request_json("GET", "test")
            
            assert dashboard.oanda.health_state == "RED"

def test_defensive_mode_activation_on_red_health(dashboard):
    dashboard.oanda.health_state = "RED"
    dashboard.perform_continuous_reconciliation()
    
    assert dashboard._CSS_SESSION_LOCK["locked"] is True
    assert dashboard._CSS_SESSION_LOCK["reason"] == "BROKER_HEALTH_RED"

def test_broker_recovery(dashboard):
    dashboard.oanda.health_state = "DEGRADED"
    dashboard.oanda.consecutive_failures = 3
    
    with patch("backend.app.brokers.oanda_adapter.requests.request") as mock_req:
        mock_req.return_value = MagicMock(status_code=200, json=lambda: {"ok": True})
        
        resp = dashboard.oanda._request_json("GET", "test")
        
        assert resp["ok"] is True
        assert dashboard.oanda.health_state == "GREEN"
        assert dashboard.oanda.consecutive_failures == 0

def test_insufficient_margin_response(dashboard):
    with patch("backend.app.brokers.oanda_adapter.requests.request") as mock_req:
        mock_req.return_value = MagicMock(
            status_code=400,
            json=lambda: {"errorMessage": "INSUFFICIENT MARGIN"}
        )
        
        resp = dashboard.oanda._request_json("POST", "orders", {"units": 100})
        
        assert resp["ok"] is False
        assert resp["error"] == "insufficient_margin"
        assert dashboard.oanda.margin_rejection_lock is True

def test_prevent_orders_after_margin_rejection(dashboard):
    dashboard.oanda.margin_rejection_lock = True
    
    with patch("backend.app.brokers.oanda_adapter.requests.request") as mock_req:
        resp = dashboard.oanda._request_json("POST", "orders", {"units": 100})
        
        assert resp["ok"] is False
        assert resp["error"] == "margin_rejection_lock_active"
        mock_req.assert_not_called()
