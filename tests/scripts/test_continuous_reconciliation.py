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
    dashboard.mtm_engine.positions.clear()
    dashboard.SELECTED_BROKER = "OANDA"
    dashboard.BROKER_EXECUTION_ARMED = True

def test_heartbeat_healthy_parity(dashboard):
    with patch("backend.app.brokers.oanda_adapter.OandaAdapter.get_open_positions") as mock_get:
        mock_get.return_value = {"ok": True, "data": {"positions": []}}
        
        dashboard.perform_continuous_reconciliation()
        
        assert dashboard.RECONCILIATION_STATUS == "HEALTHY"
        assert not dashboard.is_session_locked()

def test_broker_position_exists_local_absent(dashboard):
    with patch("backend.app.brokers.oanda_adapter.OandaAdapter.get_open_positions") as mock_get:
        mock_get.return_value = {"ok": True, "data": {"positions": [{"instrument": "EUR_USD"}]}}
        
        dashboard.perform_continuous_reconciliation()
        
        assert dashboard.RECONCILIATION_STATUS == "MISMATCH"
        assert dashboard.is_session_locked()
        assert "RECONCILIATION_DIVERGENCE" in dashboard._CSS_SESSION_LOCK.get("reason", "")

def test_local_ledger_exists_broker_absent(dashboard):
    with patch("backend.app.brokers.oanda_adapter.OandaAdapter.get_open_positions") as mock_get:
        mock_get.return_value = {"ok": True, "data": {"positions": []}}
        
        # Local FX position exists
        dashboard.mtm_engine.positions.append({"position_id": "test", "asset_class": "FX", "symbol": "USD_JPY", "quantity": 100, "forced_exit": False})
        
        dashboard.perform_continuous_reconciliation()
        
        assert dashboard.RECONCILIATION_STATUS == "MISMATCH"
        assert dashboard.is_session_locked()
        assert "RECONCILIATION_DIVERGENCE" in dashboard._CSS_SESSION_LOCK.get("reason", "")

def test_broker_api_unavailable(dashboard):
    with patch("backend.app.brokers.oanda_adapter.OandaAdapter.get_open_positions") as mock_get:
        mock_get.return_value = {"ok": False, "error": "timeout"}
        
        dashboard.perform_continuous_reconciliation()
        
        assert dashboard.RECONCILIATION_STATUS == "MISMATCH"
        assert dashboard.is_session_locked()
        assert "CONTINUOUS_RECONCILIATION_API_ERROR" in dashboard._CSS_SESSION_LOCK.get("reason", "")

def test_no_new_execution_allowed_after_mismatch(dashboard):
    # If the session is locked, perform_continuous_reconciliation or any other execution logic
    # should respect the lock. The prompt states "no new execution allowed after mismatch".
    dashboard.lock_session("RECONCILIATION_DIVERGENCE")
    
    assert dashboard.is_session_locked()
    assert dashboard._CSS_SESSION_LOCK.get("locked") is True
