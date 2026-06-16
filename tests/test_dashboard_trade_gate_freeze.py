import ast
import time
from pathlib import Path
from typing import Any

from backend.governance.css_unified_trade_gate import CSSUnifiedTradeGate
from backend.governance.css_gate_dashboard_adapter import CSSGateDashboardAdapter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_PATH = PROJECT_ROOT / "scripts" / "css_live_dashboard.py"

def _load_dashboard_gate_helpers():
    source = DASHBOARD_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    wanted = {
        "approve_trade_before_register",
    }

    nodes = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in wanted
    ]
    module = ast.Module(body=nodes, type_ignores=[])
    ast.fix_missing_locations(module)

    # Provide the necessary globals
    backend_gate = CSSUnifiedTradeGate()
    adapter = CSSGateDashboardAdapter(backend_gate)

    namespace = {
        "Any": Any,
        "SESSION_USER_CTX": {
            "session_id": "TEST-123",
            "session_status": {"active": True},
            "role_profile": {
                "role": "TRADER",
                "can_execute_paper_trading": True,
                "can_use_live_broker_mode": False,
                "can_execute_live_trading": False
            },
            "created": time.time()
        },
        "SELECTED_BROKER_MODE": "paper",
        "SELECTED_BROKER": "OANDA",
        "ENGINE_MODE": "SAFE",
        "is_session_locked": lambda: False,
        "_dashboard_portfolio_state_for_gate": lambda: {"crypto": 0},
        "css_unified_trade_gate": adapter,
        "audit_ledger": type("MockAudit", (), {"record": lambda *a, **k: None})()
    }
    exec(compile(module, str(DASHBOARD_PATH), "exec"), namespace)
    return namespace

def test_dashboard_gate_output_shape():
    ns = _load_dashboard_gate_helpers()
    approved, reason = ns["approve_trade_before_register"](
        asset_class="crypto",
        symbol="BTC-USD",
        sig=0.5,
        prob=0.9
    )
    assert isinstance(approved, bool)
    assert isinstance(reason, str)
    assert approved is True
    assert reason == "UNIFIED_GATE_APPROVED"

def test_dashboard_gate_precheck_session_locked():
    ns = _load_dashboard_gate_helpers()
    ns["is_session_locked"] = lambda: True
    approved, reason = ns["approve_trade_before_register"]("crypto", "BTC-USD", 0.5, 0.9)
    assert approved is False
    assert reason == "SESSION_LOCKED_DEFENSIVE_MODE"

def test_dashboard_gate_precheck_unsupported_asset():
    ns = _load_dashboard_gate_helpers()
    approved, reason = ns["approve_trade_before_register"]("realestate", "HOUSE", 0.5, 0.9)
    assert approved is False
    assert reason == "UNSUPPORTED_ASSET_CLASS_REALESTATE"

def test_canonical_gate_adapter_matches_shape():
    backend_gate = CSSUnifiedTradeGate()
    adapter = CSSGateDashboardAdapter(backend_gate)
    
    session = {"session_id": "TEST-123", "created": time.time()}
    role_profile = {"role": "TRADER", "can_execute_paper_trading": True}
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
    backend_gate = CSSUnifiedTradeGate()
    adapter = CSSGateDashboardAdapter(backend_gate)
    
    session = {"session_id": "TEST-123", "created": time.time()}
    role_profile = {"role": "TRADER", "can_execute_paper_trading": True}
    candidate = {"asset_class": "crypto", "symbol": "BTC-USD", "signal_score": 0.5, "prob_positive": 0.1} # Prob is 0.1!
    
    decision = adapter.approve_trade(
        candidate=candidate,
        session=session,
        role_profile=role_profile,
        portfolio_state={"crypto": 0},
        engine_mode="SAFE"
    )
    
    assert decision["approved"] is True
