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

import scripts.css_live_dashboard as dashboard

@pytest.fixture(autouse=True)
def reset_state():
    dashboard._CSS_SESSION_LOCK.clear()
    dashboard.RECONCILIATION_STATUS = "HEALTHY"
    dashboard.mtm_engine.positions.clear()
    dashboard.SELECTED_BROKER = "OANDA"
    dashboard.BROKER_EXECUTION_ARMED = True
    dashboard.oanda.health_state = "GREEN"
    dashboard.repair_engine.records.clear()
    
    dashboard._IN_FLIGHT_ORDERS.clear()
    dashboard._DIVERGENCE_STATE = {
        "first_detected": None,
        "count": 0,
        "type": None,
        "last_simulation": None,
        "confirmed_count": 0,
        "pending_count": 0
    }

def test_orphan_detection_and_two_cycle_confirmation():
    # 1. No mismatch initially
    with patch("backend.app.brokers.oanda_adapter.OandaAdapter.get_open_positions") as mock_get:
        mock_get.return_value = {"ok": True, "data": {"positions": []}}
        dashboard.perform_continuous_reconciliation()
        assert dashboard._DIVERGENCE_STATE["count"] == 0

    # 2. First cycle mismatch (orphan)
    with patch("backend.app.brokers.oanda_adapter.OandaAdapter.get_open_positions") as mock_get:
        mock_get.return_value = {"ok": True, "data": {"positions": [{"instrument": "EUR_USD", "units": "100"}]}}
        dashboard.perform_continuous_reconciliation()
        
        assert dashboard._DIVERGENCE_STATE["count"] == 1
        assert dashboard._DIVERGENCE_STATE["type"] == "ORPHAN_BROKER_POSITION"
        assert dashboard._DIVERGENCE_STATE["confirmed_count"] == 0
        
        # Repair record created but not simulated
        assert len(dashboard.repair_engine.records) == 1
        assert dashboard.repair_engine.records[0]["category"] == "ORPHAN_BROKER_POSITION"
        assert dashboard.repair_engine.records[0]["status"] == "OPEN"

    # 3. Second cycle mismatch (orphan)
    with patch("backend.app.brokers.oanda_adapter.OandaAdapter.get_open_positions") as mock_get:
        mock_get.return_value = {"ok": True, "data": {"positions": [{"instrument": "EUR_USD", "units": "100"}]}}
        dashboard.perform_continuous_reconciliation()
        
        assert dashboard._DIVERGENCE_STATE["count"] == 2
        assert dashboard._DIVERGENCE_STATE["confirmed_count"] == 1
        assert dashboard._DIVERGENCE_STATE["pending_count"] == 1
        
        # New record for simulation
        assert len(dashboard.repair_engine.records) == 2
        sim_record = dashboard.repair_engine.records[1]
        assert sim_record["status"] == "AUTO_FLATTEN_SIMULATED"
        assert "SIMULATED_ONLY" in sim_record["details"]
        assert "delta=100" in sim_record["details"]
        
        # Session is locked
        assert dashboard.is_session_locked()
        assert dashboard._CSS_SESSION_LOCK.get("reason") == "PENDING_AUTO_FLATTEN"

def test_in_flight_order_suppression():
    dashboard.register_in_flight_order("order-123")
    assert dashboard.has_in_flight_orders()

    with patch("backend.app.brokers.oanda_adapter.OandaAdapter.get_open_positions") as mock_get:
        mock_get.return_value = {"ok": True, "data": {"positions": [{"instrument": "EUR_USD", "units": "100"}]}}
        dashboard.perform_continuous_reconciliation()
        
        # Count remains 0 due to suppression
        assert dashboard._DIVERGENCE_STATE["count"] == 0
        
        # Record is still created, but simulation logic never increments
        assert len(dashboard.repair_engine.records) == 1
        
    dashboard.clear_in_flight_order("order-123")
    assert not dashboard.has_in_flight_orders()

def test_ghost_local_position_exclusion():
    # Broker has 0, ledger has 1
    dashboard.mtm_engine.positions.append({
        "position_id": "pos-1", "asset_class": "FX", "symbol": "USD_JPY", "quantity": 100, "forced_exit": False
    })
    
    with patch("backend.app.brokers.oanda_adapter.OandaAdapter.get_open_positions") as mock_get:
        mock_get.return_value = {"ok": True, "data": {"positions": []}}
        
        dashboard.perform_continuous_reconciliation()
        
        assert dashboard._DIVERGENCE_STATE["count"] == 1
        assert dashboard._DIVERGENCE_STATE["type"] == "GHOST_LOCAL_POSITION"
        
        # Second cycle
        dashboard.perform_continuous_reconciliation()
        
        assert dashboard._DIVERGENCE_STATE["count"] == 2
        # Ghost should NOT trigger auto-flatten simulation
        assert dashboard._DIVERGENCE_STATE["pending_count"] == 0
        assert dashboard._DIVERGENCE_STATE["confirmed_count"] == 0
