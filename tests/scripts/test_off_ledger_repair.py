import pytest
import os
import sys

os.environ["CSS_TEST_MODE"] = "1"
os.environ["DATA_PROVIDER"] = "SIMULATED"
os.environ["OANDA_API_KEY"] = "mock"
os.environ["OANDA_ACCOUNT_ID"] = "mock_acc"
os.environ["OANDA_BASE_URL"] = "http://mock.com"
os.environ["OANDA_ENV"] = "practice"

import json
from unittest.mock import patch, MagicMock

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

@pytest.fixture
def clean_repair_engine(dashboard):
    if dashboard.repair_engine.records_file.exists():
        os.remove(dashboard.repair_engine.records_file)
    dashboard.repair_engine.records = []
    dashboard.RECONCILIATION_STATUS = "HEALTHY"
    dashboard.SESSION_USER_CTX = {"session_id": "test_123"}
    dashboard.SELECTED_BROKER = "OANDA"
    dashboard.BROKER_EXECUTION_ARMED = True
    yield dashboard.repair_engine
    if dashboard.repair_engine.records_file.exists():
        os.remove(dashboard.repair_engine.records_file)
    dashboard.repair_engine.records = []

def test_repair_record_creation_and_persistence(clean_repair_engine, dashboard):
    record_id = clean_repair_engine.create_record("ORPHAN_BROKER_POSITION", {"symbol": "EUR_USD"})
    assert record_id.startswith("REP-")
    assert len(clean_repair_engine.records) == 1
    assert clean_repair_engine.records[0]["status"] == "OPEN"
    
    # Verify persistence
    engine2 = dashboard.RepairEngine()
    assert len(engine2.records) == 1
    assert engine2.records[0]["record_id"] == record_id

def test_repair_status_transitions(clean_repair_engine, dashboard):
    record_id = clean_repair_engine.create_record("GHOST_LOCAL_POSITION", {"symbol": "USD_JPY"})
    assert clean_repair_engine.has_open_records() is True
    
    success = clean_repair_engine.resolve_record(record_id, "OFF_LEDGER_CLOSE", "Closed via web portal")
    assert success is True
    assert clean_repair_engine.has_open_records() is False
    assert clean_repair_engine.records[0]["status"] == "REPAIRED"
    assert clean_repair_engine.records[0]["resolution_note"] == "[OFF_LEDGER_CLOSE] Closed via web portal"

def test_detect_divergences_orphan_broker(dashboard):
    local = []
    broker = [{"instrument": "EUR_USD", "long": {"units": "100"}}]
    
    divs = dashboard.detect_divergences(local, broker)
    assert len(divs) == 1
    assert divs[0][0] == "ORPHAN_BROKER_POSITION"
    assert divs[0][1]["symbol"] == "EUR_USD"

def test_detect_divergences_ghost_local(dashboard):
    local = [{"asset_class": "FX", "symbol": "USD_JPY", "quantity": 100}]
    broker = []
    
    divs = dashboard.detect_divergences(local, broker)
    assert len(divs) == 1
    assert divs[0][0] == "GHOST_LOCAL_POSITION"
    assert divs[0][1]["symbol"] == "USD_JPY"

@patch("scripts.css_live_dashboard.oanda")
@patch("scripts.css_live_dashboard.mtm_engine")
@patch("scripts.css_live_dashboard.lock_session")
def test_startup_reconciliation_locks_on_divergence(mock_lock, mock_mtm, mock_oanda, clean_repair_engine, dashboard):
    mock_oanda.get_open_positions.return_value = {
        "ok": True,
        "data": {"positions": [{"instrument": "EUR_USD"}]}
    }
    mock_mtm.positions = []
    
    dashboard.perform_startup_reconciliation()
    
    assert dashboard.RECONCILIATION_STATUS == "MISMATCH"
    mock_lock.assert_called_with("RECONCILIATION_DIVERGENCE")
    assert len(clean_repair_engine.records) == 1
    assert clean_repair_engine.records[0]["category"] == "ORPHAN_BROKER_POSITION"

@patch("scripts.css_live_dashboard.oanda")
@patch("scripts.css_live_dashboard.mtm_engine")
@patch("scripts.css_live_dashboard.lock_session")
def test_continuous_reconciliation_locks_on_divergence(mock_lock, mock_mtm, mock_oanda, clean_repair_engine, dashboard):
    mock_oanda.get_open_positions.return_value = {
        "ok": True,
        "data": {"positions": []}
    }
    mock_mtm.positions = [{"asset_class": "FX", "symbol": "USD_JPY", "quantity": 100}]
    
    dashboard.perform_continuous_reconciliation()
    
    assert dashboard.RECONCILIATION_STATUS == "MISMATCH"
    mock_lock.assert_called_with("RECONCILIATION_DIVERGENCE")
    assert len(clean_repair_engine.records) == 1
    assert clean_repair_engine.records[0]["category"] == "GHOST_LOCAL_POSITION"
