import pytest
from unittest.mock import patch, MagicMock

import os
os.environ["CSS_TEST_MODE"] = "1"
os.environ["OANDA_API_KEY"] = "mock_key"
os.environ["OANDA_ACCOUNT_ID"] = "mock_acc"
os.environ["OANDA_BASE_URL"] = "http://127.0.0.1:9999" # fast fail
os.environ["OANDA_ENV"] = "practice"
os.environ["DATA_PROVIDER"] = "SIMULATED"

from backend.app.brokers.oanda_adapter import OandaAdapter
from scripts.css_live_dashboard import perform_continuous_reconciliation, oanda, _CSS_SESSION_LOCK, lock_session
from scripts import css_live_dashboard

@pytest.fixture(autouse=True)
def reset_state():
    css_live_dashboard._CSS_SESSION_LOCK["locked"] = False
    css_live_dashboard._CSS_SESSION_LOCK["reason"] = None
    oanda.health_state = "GREEN"
    oanda.consecutive_failures = 0
    oanda.margin_rejection_lock = False
    css_live_dashboard.RECONCILIATION_STATUS = "HEALTHY"
    css_live_dashboard.SELECTED_BROKER = "OANDA"
    css_live_dashboard.BROKER_EXECUTION_ARMED = True

def test_http_429_handling_recovery():
    with patch("backend.app.brokers.oanda_adapter.requests.request") as mock_req:
        mock_req.side_effect = [
            MagicMock(status_code=429),
            MagicMock(status_code=200, json=lambda: {"test": "ok"})
        ]
        
        with patch("time.sleep") as mock_sleep:
            resp = oanda._request_json("GET", "test")
            
            assert resp["ok"] is True
            assert oanda.health_state == "GREEN"
            assert mock_req.call_count == 2
            mock_sleep.assert_called_once()

def test_retry_exhaustion_429():
    with patch("backend.app.brokers.oanda_adapter.requests.request") as mock_req:
        mock_req.return_value = MagicMock(status_code=429)
        
        with patch("time.sleep"):
            resp = oanda._request_json("GET", "test")
            
            assert resp["ok"] is False
            assert resp["error"] == "rate_limit_exhausted"
            assert oanda.consecutive_failures == 1

def test_broker_red_state_escalation():
    with patch("backend.app.brokers.oanda_adapter.requests.request") as mock_req:
        mock_req.return_value = MagicMock(status_code=500)
        
        with patch("time.sleep"):
            for _ in range(5):
                oanda._request_json("GET", "test")
            
            assert oanda.health_state == "RED"

def test_defensive_mode_activation_on_red_health():
    oanda.health_state = "RED"
    perform_continuous_reconciliation()
    
    assert css_live_dashboard._CSS_SESSION_LOCK["locked"] is True
    assert css_live_dashboard._CSS_SESSION_LOCK["reason"] == "BROKER_HEALTH_RED"

def test_broker_recovery():
    oanda.health_state = "DEGRADED"
    oanda.consecutive_failures = 3
    
    with patch("backend.app.brokers.oanda_adapter.requests.request") as mock_req:
        mock_req.return_value = MagicMock(status_code=200, json=lambda: {"ok": True})
        
        resp = oanda._request_json("GET", "test")
        
        assert resp["ok"] is True
        assert oanda.health_state == "GREEN"
        assert oanda.consecutive_failures == 0

def test_insufficient_margin_response():
    with patch("backend.app.brokers.oanda_adapter.requests.request") as mock_req:
        mock_req.return_value = MagicMock(
            status_code=400,
            json=lambda: {"errorMessage": "INSUFFICIENT MARGIN"}
        )
        
        resp = oanda._request_json("POST", "orders", {"units": 100})
        
        assert resp["ok"] is False
        assert resp["error"] == "insufficient_margin"
        assert oanda.margin_rejection_lock is True

def test_prevent_orders_after_margin_rejection():
    oanda.margin_rejection_lock = True
    
    with patch("backend.app.brokers.oanda_adapter.requests.request") as mock_req:
        resp = oanda._request_json("POST", "orders", {"units": 100})
        
        assert resp["ok"] is False
        assert resp["error"] == "margin_rejection_lock_active"
        mock_req.assert_not_called()
