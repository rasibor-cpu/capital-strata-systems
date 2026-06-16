import os
import sys
import pytest
from unittest.mock import patch, MagicMock

os.environ["CSS_TEST_MODE"] = "1"
os.environ["OANDA_API_KEY"] = "mock_key"
os.environ["OANDA_ACCOUNT_ID"] = "mock_acc"
os.environ["OANDA_BASE_URL"] = "http://mock.com"
os.environ["OANDA_ENV"] = "practice"
os.environ["DATA_PROVIDER"] = "SIMULATED" # Prevent external data fetches

@pytest.fixture(scope="module")
def dashboard():
    # Mock sign on
    mock_auth = MagicMock()
    mock_auth.await_login_ready_state.return_value = {
        "user_id": "test", 
        "role": "admin", 
        "display_name": "test", 
        "unit_code": "test", 
        "home_branch": "test"
    }
    sys.modules["dashboard.auth.css_sign_on"] = mock_auth
    
    # Mock input for interactive prompts
    sys.modules["builtins"].input = lambda prompt: "1"

    # Import dashboard once for all tests in this module
    import scripts.css_live_dashboard as db
    yield db

@pytest.fixture(autouse=True)
def reset_dashboard_state(dashboard):
    # Reset lock and state before each test
    dashboard._CSS_SESSION_LOCK.clear()
    dashboard.RECONCILIATION_STATUS = "HEALTHY"
    dashboard.mtm_engine.positions.clear()
    dashboard.SELECTED_BROKER = "OANDA"
    dashboard.BROKER_EXECUTION_ARMED = True

def test_startup_parity(dashboard):
    with patch("backend.app.brokers.oanda_adapter.OandaAdapter.get_open_positions") as mock_get:
        # Mock OANDA returning 0 positions
        mock_get.return_value = {"ok": True, "data": {"positions": []}}
        
        dashboard.perform_startup_reconciliation()
        
        assert dashboard.RECONCILIATION_STATUS == "HEALTHY"
        assert not dashboard.is_session_locked()

def test_broker_position_exists_local_absent(dashboard):
    with patch("backend.app.brokers.oanda_adapter.OandaAdapter.get_open_positions") as mock_get:
        # Mock OANDA returning 1 position
        mock_get.return_value = {"ok": True, "data": {"positions": [{"instrument": "EUR_USD"}]}}
        
        dashboard.perform_startup_reconciliation()
        
        assert dashboard.RECONCILIATION_STATUS == "MISMATCH"
        assert dashboard.is_session_locked()
        assert "RECONCILIATION_MISMATCH" in dashboard._CSS_SESSION_LOCK.get("reason", "")

def test_local_position_exists_broker_absent(dashboard):
    with patch("backend.app.brokers.oanda_adapter.OandaAdapter.get_open_positions") as mock_get:
        # Mock OANDA returning 0 positions
        mock_get.return_value = {"ok": True, "data": {"positions": []}}
        
        # Mock local having 1 FX position
        dashboard.mtm_engine.positions.append({"position_id": "test", "asset_class": "FX", "forced_exit": False})
        
        dashboard.perform_startup_reconciliation()
        
        assert dashboard.RECONCILIATION_STATUS == "MISMATCH"
        assert dashboard.is_session_locked()
        assert "RECONCILIATION_MISMATCH" in dashboard._CSS_SESSION_LOCK.get("reason", "")

def test_reconciliation_api_error(dashboard):
    with patch("backend.app.brokers.oanda_adapter.OandaAdapter.get_open_positions") as mock_get:
        # Mock OANDA returning API error
        mock_get.return_value = {"ok": False, "error": "http_500"}
        
        dashboard.perform_startup_reconciliation()
        
        assert dashboard.RECONCILIATION_STATUS == "MISMATCH"
        assert dashboard.is_session_locked()
        assert "RECONCILIATION_API_ERROR" in dashboard._CSS_SESSION_LOCK.get("reason", "")

def test_startup_lock_behavior(dashboard):
    # If a session is locked by reconciliation, it should remain locked and enforce defensive mode
    dashboard.lock_session("RECONCILIATION_MISMATCH")
    assert dashboard.is_session_locked()
    assert dashboard._CSS_SESSION_LOCK.get("locked") is True
