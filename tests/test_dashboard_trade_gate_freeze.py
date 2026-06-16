import pytest
from unittest.mock import patch
import time

from scripts import css_live_dashboard
from backend.governance.css_unified_trade_gate import CSSUnifiedTradeGate
from backend.governance.css_gate_dashboard_adapter import CSSGateDashboardAdapter

@pytest.fixture
def mock_dashboard_env():
    with patch("scripts.css_live_dashboard.SESSION_USER_CTX", {
        "session_id": "TEST-123",
        "session_status": {"active": True},
        "role_profile": {
            "role": "TRADER",
            "can_execute_paper_trading": True,
            "can_use_live_broker_mode": False,
            "can_execute_live_trading": False
        },
        "created": time.time()
    }), \
    patch("scripts.css_live_dashboard.SELECTED_BROKER_MODE", "paper"), \
    patch("scripts.css_live_dashboard.ENGINE_MODE", "SAFE"), \
    patch("scripts.css_live_dashboard.is_session_locked", return_value=False), \
    patch("scripts.css_live_dashboard._dashboard_portfolio_state_for_gate", return_value={"crypto": 0}), \
    patch("scripts.css_live_dashboard.audit_ledger"):
        yield

def test_dashboard_gate_output_shape(mock_dashboard_env):
    approved, reason = css_live_dashboard.approve_trade_before_register(
        asset_class="crypto",
        symbol="BTC-USD",
        sig=0.5,
        prob=0.9
    )
    # Based on adapter behavior, it should be approved if expected_value > cost and probability >= threshold
    # Cost defaults to 0.0, expected_value defaults to sig (0.5), threshold for SAFE is 0.65
    assert isinstance(approved, bool)
    assert isinstance(reason, str)
    assert approved is True
    assert reason == "UNIFIED_GATE_APPROVED"

def test_dashboard_gate_precheck_session_locked(mock_dashboard_env):
    with patch("scripts.css_live_dashboard.is_session_locked", return_value=True):
        approved, reason = css_live_dashboard.approve_trade_before_register("crypto", "BTC-USD", 0.5, 0.9)
        assert approved is False
        assert reason == "SESSION_LOCKED_DEFENSIVE_MODE"

def test_dashboard_gate_precheck_unsupported_asset(mock_dashboard_env):
    approved, reason = css_live_dashboard.approve_trade_before_register("realestate", "HOUSE", 0.5, 0.9)
    assert approved is False
    assert reason == "UNSUPPORTED_ASSET_CLASS_REALESTATE"

def test_canonical_gate_adapter_matches_shape():
    backend_gate = CSSUnifiedTradeGate()
    adapter = CSSGateDashboardAdapter(backend_gate)
    
    session = {"session_id": "TEST-123", "created": time.time()}
    role_profile = {"role": "TRADER"}
    candidate = {"asset_class": "crypto", "symbol": "BTC-USD", "signal_score": 0.5, "prob_positive": 0.9}
    
    decision = adapter.approve_trade(
        candidate=candidate,
        session=session,
        role_profile=role_profile,
        portfolio_state={"crypto": 0},
        engine_mode="SAFE"
    )
    
    assert isinstance(decision, dict)
    assert "approved" in decision
    assert "reason" in decision
    assert "backend_reason" in decision
    assert "backend_details" in decision
    assert decision["approved"] is True
    assert decision["reason"] == "UNIFIED_GATE_APPROVED"

def test_mismatch_identification_probability_thresholds():
    # Adapter artificially bumps probability to meet threshold if missing, wait:
    # `threshold = thresholds.get(str(engine_mode or "").upper(), 0.58)`
    # `return max(float(probability), threshold)`
    # This means the adapter ALWAYS bypasses the backend probability check!
    backend_gate = CSSUnifiedTradeGate()
    adapter = CSSGateDashboardAdapter(backend_gate)
    
    session = {"session_id": "TEST-123", "created": time.time()}
    role_profile = {"role": "TRADER"}
    candidate = {"asset_class": "crypto", "symbol": "BTC-USD", "signal_score": 0.5, "prob_positive": 0.1} # Prob is 0.1!
    
    decision = adapter.approve_trade(
        candidate=candidate,
        session=session,
        role_profile=role_profile,
        portfolio_state={"crypto": 0},
        engine_mode="SAFE"
    )
    # The adapter forces probability to 0.65 for SAFE mode. The backend requires 0.65.
    # Therefore, the backend approves it! This is a mismatch in behavior from pure backend gate.
    assert decision["approved"] is True
