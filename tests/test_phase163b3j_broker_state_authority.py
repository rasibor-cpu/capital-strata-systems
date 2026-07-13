import os
import sys
import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone

@pytest.fixture(scope="module")
def dashboard():
    # Save original env to prevent contamination of other tests during execution
    old_env = dict(os.environ)
    
    os.environ["CSS_TEST_MODE"] = "1"
    os.environ["OANDA_API_KEY"] = "mock_key"
    os.environ["OANDA_ACCOUNT_ID"] = "mock_acc"
    os.environ["OANDA_BASE_URL"] = "http://mock.com"
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

    import scripts.css_live_dashboard as db
    yield db
    
    # Restore original environment variables
    os.environ.clear()
    os.environ.update(old_env)

def test_successful_validation_propagation(dashboard):
    # Reset sequence
    if "PCNRASS_VALIDATION_SEQUENCE" in globals():
        del globals()["PCNRASS_VALIDATION_SEQUENCE"]
        
    dashboard.COINBASE_READ_ONLY_STATUS = {}
    
    mock_validation = {
        "validation_status": "PASS",
        "api_reachable": True,
        "authenticated": True,
        "account_loaded": True,
        "balances_loaded": True,
        "products_loaded": 936,
        "market_data_loaded": True,
        "validation_timestamp": "2026-07-13T01:00:00Z",
        "failure_reasons": [],
        "broker_operational_status": {
            "equity": 100.45,
            "cash": 100.45,
            "buying_power": 100.45,
            "available_balance": 100.45
        }
    }
    
    dashboard.pcnrass_update_authoritative_broker_state(mock_validation, "COINBASE_LIVE_VALIDATOR")
    
    status = dashboard.COINBASE_READ_ONLY_STATUS
    assert status["broker_connected"] is True
    assert status["broker_authenticated"] is True
    assert status["credential_status"] == "PASS"
    assert status["auth_status"] == "PASS"
    assert status["connection_status"] == "PASS"
    assert status["products_loaded"] == 936
    assert status["market_data_status"] == "OK"
    assert status["connection_error"] == ""
    assert status["generated_at"] == "2026-07-13T01:00:00Z"
    assert status["validation_completed"] is True
    assert status["validation_source"] == "COINBASE_LIVE_VALIDATOR"
    assert status["validation_sequence"] == 1
    assert status["last_successful_validation_at"] == "2026-07-13T01:00:00Z"
    assert status["readiness_state"] == "FULLY_OPERATIONAL"
    assert status["go_no_go"] == "GO"
    assert status["account_equity"] == 100.45
    assert status["cash"] == 100.45
    assert status["buying_power"] == 100.45
    assert status["available_balance"] == 100.45

def test_failed_validation_propagation(dashboard):
    dashboard.COINBASE_READ_ONLY_STATUS = {
        "account_equity": 100.45,
        "cash": 100.45,
        "buying_power": 100.45,
        "available_balance": 100.45
    }
    
    mock_failure = {
        "validation_status": "FAIL_CLOSED",
        "api_reachable": False,
        "authenticated": False,
        "account_loaded": False,
        "balances_loaded": False,
        "products_loaded": 0,
        "market_data_loaded": False,
        "validation_timestamp": "2026-07-13T01:05:00Z",
        "failure_reasons": [{"message": "HTTP 401 Unauthorized"}],
        "broker_operational_status": {}
    }
    
    dashboard.pcnrass_update_authoritative_broker_state(mock_failure, "COINBASE_LIVE_VALIDATOR")
    
    status = dashboard.COINBASE_READ_ONLY_STATUS
    assert status["broker_connected"] is False
    assert status["broker_authenticated"] is False
    assert status["credential_status"] == "FAIL"
    assert status["auth_status"] == "FAIL"
    assert status["connection_status"] == "FAIL"
    assert status["products_loaded"] == 0
    assert status["market_data_status"] == "FAIL"
    assert status["connection_error"] == "HTTP 401 Unauthorized"
    assert status["readiness_state"] == "FAIL_CLOSED"
    assert status["go_no_go"] == "NO GO"
    
    # Verify prior success balances are cleared/nill-out to prevent leakage
    assert status["account_equity"] is None
    assert status["cash"] is None
    assert status["buying_power"] is None
    assert status["available_balance"] is None

def test_partial_result_rejection(dashboard):
    dashboard.COINBASE_READ_ONLY_STATUS = {
        "readiness_state": "FAIL_CLOSED",
        "go_no_go": "NO GO"
    }
    
    # An empty or None result should not update the state or restore success
    dashboard.pcnrass_update_authoritative_broker_state(None, "COINBASE_LIVE_VALIDATOR")
    dashboard.pcnrass_update_authoritative_broker_state({}, "COINBASE_LIVE_VALIDATOR")
    
    status = dashboard.COINBASE_READ_ONLY_STATUS
    assert status["readiness_state"] == "FAIL_CLOSED"
    assert status["go_no_go"] == "NO GO"

def test_timestamp_sequence_ordering(dashboard):
    dashboard.COINBASE_READ_ONLY_STATUS = {}
    
    mock_v1 = {
        "validation_status": "PASS",
        "validation_timestamp": "2026-07-13T01:10:00Z"
    }
    mock_v2 = {
        "validation_status": "PASS",
        "validation_timestamp": "2026-07-13T01:12:00Z"
    }
    
    dashboard.pcnrass_update_authoritative_broker_state(mock_v1, "COINBASE_LIVE_VALIDATOR")
    seq1 = dashboard.COINBASE_READ_ONLY_STATUS["validation_sequence"]
    
    dashboard.pcnrass_update_authoritative_broker_state(mock_v2, "COINBASE_LIVE_VALIDATOR")
    seq2 = dashboard.COINBASE_READ_ONLY_STATUS["validation_sequence"]
    
    assert seq2 == seq1 + 1
    assert dashboard.COINBASE_READ_ONLY_STATUS["generated_at"] == "2026-07-13T01:12:00Z"
def test_unchanged_execution_safety_controls(dashboard):
    dashboard.COINBASE_READ_ONLY_STATUS = {
        "execution_allowed": False,
        "advisory_only": True,
    }
    mock_validation = {
        "validation_status": "PASS",
        "api_reachable": True,
        "authenticated": True
    }
    dashboard.pcnrass_update_authoritative_broker_state(mock_validation, "COINBASE_LIVE_VALIDATOR")
    
    # Safety flags must remain safe in COINBASE_READ_ONLY_STATUS and global configs
    assert dashboard.COINBASE_READ_ONLY_STATUS.get("execution_allowed") is False
    assert dashboard.COINBASE_READ_ONLY_STATUS.get("advisory_only") is True
    assert dashboard.BROKER_EXECUTION_ARMED is False


