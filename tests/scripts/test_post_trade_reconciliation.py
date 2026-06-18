import os
import sys
import pytest
from unittest.mock import patch, MagicMock

os.environ["CSS_TEST_MODE"] = "1"
os.environ["OANDA_API_KEY"] = "mock_key"
os.environ["OANDA_ACCOUNT_ID"] = "mock_acc"
os.environ["OANDA_BASE_URL"] = "http://mock.com"
os.environ["OANDA_ENV"] = "practice"
os.environ["DATA_PROVIDER"] = "SIMULATED"

@pytest.fixture(scope="module")
def dashboard():
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

    import scripts.css_live_dashboard as db
    yield db

@pytest.fixture(autouse=True)
def reset_dashboard_state(dashboard):
    dashboard._CSS_SESSION_LOCK.clear()
    dashboard.RECONCILIATION_STATUS = "HEALTHY"

def test_post_trade_success(dashboard):
    with patch("backend.app.brokers.oanda_adapter.OandaAdapter.get_open_trades") as mock_get:
        mock_get.return_value = {
            "ok": True, 
            "data": {
                "trades": [
                    {"id": "12345", "instrument": "EUR_USD", "currentUnits": "10"}
                ]
            }
        }
        
        dashboard.perform_post_trade_verification("12345", "EUR_USD", "10")
        
        assert dashboard.RECONCILIATION_STATUS == "HEALTHY"
        assert not dashboard.is_session_locked()

def test_post_trade_missing_trade(dashboard):
    with patch("backend.app.brokers.oanda_adapter.OandaAdapter.get_open_trades") as mock_get:
        mock_get.return_value = {
            "ok": True, 
            "data": {
                "trades": [
                    {"id": "99999", "instrument": "EUR_USD", "currentUnits": "10"}
                ]
            }
        }
        
        dashboard.perform_post_trade_verification("12345", "EUR_USD", "10")
        
        assert dashboard.RECONCILIATION_STATUS == "MISMATCH"
        assert dashboard.is_session_locked()
        assert "POST_TRADE_VERIFICATION_MISSING_TRADE" in dashboard._CSS_SESSION_LOCK.get("reason", "")

def test_post_trade_mismatched_trade(dashboard):
    with patch("backend.app.brokers.oanda_adapter.OandaAdapter.get_open_trades") as mock_get:
        # Instrument mismatch
        mock_get.return_value = {
            "ok": True, 
            "data": {
                "trades": [
                    {"id": "12345", "instrument": "GBP_USD", "currentUnits": "10"}
                ]
            }
        }
        
        dashboard.perform_post_trade_verification("12345", "EUR_USD", "10")
        
        assert dashboard.RECONCILIATION_STATUS == "MISMATCH"
        assert dashboard.is_session_locked()
        assert "POST_TRADE_VERIFICATION_MISMATCH" in dashboard._CSS_SESSION_LOCK.get("reason", "")

    dashboard._CSS_SESSION_LOCK.clear()
    dashboard.RECONCILIATION_STATUS = "HEALTHY"

    with patch("backend.app.brokers.oanda_adapter.OandaAdapter.get_open_trades") as mock_get:
        # Units mismatch
        mock_get.return_value = {
            "ok": True, 
            "data": {
                "trades": [
                    {"id": "12345", "instrument": "EUR_USD", "currentUnits": "20"}
                ]
            }
        }
        
        dashboard.perform_post_trade_verification("12345", "EUR_USD", "10")
        
        assert dashboard.RECONCILIATION_STATUS == "MISMATCH"
        assert dashboard.is_session_locked()
        assert "POST_TRADE_VERIFICATION_MISMATCH" in dashboard._CSS_SESSION_LOCK.get("reason", "")

def test_post_trade_api_timeout(dashboard):
    with patch("backend.app.brokers.oanda_adapter.OandaAdapter.get_open_trades") as mock_get:
        mock_get.return_value = {"ok": False, "error": "timeout"}
        
        dashboard.perform_post_trade_verification("12345", "EUR_USD", "10")
        
        assert dashboard.RECONCILIATION_STATUS == "MISMATCH"
        assert dashboard.is_session_locked()
        assert "POST_TRADE_VERIFICATION_API_ERROR" in dashboard._CSS_SESSION_LOCK.get("reason", "")
