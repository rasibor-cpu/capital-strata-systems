import pytest
from dashboard.runtime.dashboard_state import DashboardState
from dashboard.runtime.frontend_contract import build_frontend_payload, CONTRACT_VERSION, CONTRACT_NAME
from dashboard.runtime.payload_validator import FrontendPayloadValidator

def test_frontend_contract_structure():
    state = DashboardState()
    payload = build_frontend_payload(state)
    
    # 1. Structural Checks
    assert payload["payload_version"] == CONTRACT_VERSION
    assert payload["contract_name"] == CONTRACT_NAME
    assert payload["contract_version"] == CONTRACT_VERSION
    assert "schema_metadata" in payload
    assert "strict_typing" in payload["schema_metadata"]
    
    # 2. Sections check
    assert "sections" in payload
    sections = payload["sections"]
    assert "account_summary" in sections
    assert "pnl_summary" in sections
    assert "broker" in sections

def test_frontend_payload_validator_success():
    state = DashboardState()
    payload = build_frontend_payload(state)
    
    validator = FrontendPayloadValidator()
    assert validator.validate(payload) is True

def test_frontend_payload_validator_fails_safely():
    validator = FrontendPayloadValidator()
    bad_payload = {"random": "data"}
    assert validator.validate(bad_payload) is False

def test_frontend_payload_validator_missing_section():
    state = DashboardState()
    payload = build_frontend_payload(state)
    del payload["sections"]["account_summary"]
    
    validator = FrontendPayloadValidator()
    assert validator.validate(payload) is False

def test_frontend_payload_validator_type_error():
    state = DashboardState()
    payload = build_frontend_payload(state)
    payload["sections"]["pnl_summary"]["realized_pnl"] = [1, 2, 3] # invalid type
    
    validator = FrontendPayloadValidator()
    assert validator.validate(payload) is False
