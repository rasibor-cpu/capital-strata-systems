import ast
import time
from pathlib import Path
from types import SimpleNamespace

from backend.governance.css_gate_dashboard_adapter import CSSGateDashboardAdapter
from backend.governance.css_unified_trade_gate import CSSUnifiedTradeGate


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_PATH = PROJECT_ROOT / "scripts" / "css_live_dashboard.py"


class RecordingBackendGate:
    def __init__(self, decision=None):
        self.calls = []
        self.decision = decision or SimpleNamespace(
            approved=True,
            reason="backend approved",
            details={"source": "backend"},
        )

    def approve_trade(self, **kwargs):
        self.calls.append(kwargs)
        return self.decision


class RecordingDashboardGate:
    def __init__(self, decision=None):
        self.calls = []
        self.decision = decision or {
            "approved": True,
            "reason": "UNIFIED_GATE_APPROVED",
            "backend_reason": "backend approved",
            "backend_details": {"source": "backend"},
        }

    def approve_trade(self, **kwargs):
        self.calls.append(kwargs)
        return self.decision


class AuditLedgerRecorder:
    def __init__(self):
        self.records = []

    def record(self, *args):
        self.records.append(args)


class MTMEngineStub:
    def count_open_positions_by_asset(self):
        return {
            "CRYPTO": 1,
            "FX": 2,
            "FUTURES": 0,
            "OPTIONS": 1,
        }


def _dashboard_gate_namespace(*, session_locked=False, role_profile=None, gate=None):
    source = DASHBOARD_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    wanted = {
        "_dashboard_portfolio_state_for_gate",
        "approve_trade_before_register",
    }
    nodes = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in wanted
    ]
    module = ast.Module(body=nodes, type_ignores=[])
    ast.fix_missing_locations(module)

    role_profile = role_profile or {"can_execute_paper_trading": True}
    namespace = {
        "mtm_engine": MTMEngineStub(),
        "SESSION_USER_CTX": {
            "user_id": "operator",
            "session_id": "session-1",
            "session_created": time.time(),
            "session_status": {
                "active": True,
                "created": time.time(),
            },
            "role": "TRADER",
            "role_profile": role_profile,
        },
        "SELECTED_BROKER": "NONE",
        "SELECTED_BROKER_MODE": "paper",
        "ENGINE_MODE": "BALANCED",
        "is_session_locked": lambda: session_locked,
        "audit_ledger": AuditLedgerRecorder(),
        "css_unified_trade_gate": gate or RecordingDashboardGate(),
    }
    exec(compile(module, str(DASHBOARD_PATH), "exec"), namespace)
    return namespace


def test_adapter_maps_session_created_from_direct_field():
    backend = RecordingBackendGate()
    adapter = CSSGateDashboardAdapter(backend)
    created = time.time()

    adapter.approve_trade(
        candidate={"asset_class": "CRYPTO", "signal_score": 10.0, "prob_positive": 0.5},
        session={"role": "TRADER", "created": created},
        role_profile={},
        portfolio_state={"CRYPTO": 1},
        engine_mode="BALANCED",
    )

    assert backend.calls[0]["session"]["created"] == created


def test_adapter_maps_session_created_from_session_created_field():
    backend = RecordingBackendGate()
    adapter = CSSGateDashboardAdapter(backend)
    created = time.time()

    adapter.approve_trade(
        candidate={"asset_class": "FX", "signal_score": 10.0, "prob_positive": 0.5},
        session={"role": "TRADER", "session_created": created},
        role_profile={},
        portfolio_state={"FX": 1},
        engine_mode="BALANCED",
    )

    assert backend.calls[0]["session"]["created"] == created


def test_adapter_maps_session_created_from_session_status():
    backend = RecordingBackendGate()
    adapter = CSSGateDashboardAdapter(backend)
    created = time.time()

    adapter.approve_trade(
        candidate={"asset_class": "OPTIONS", "signal_score": 10.0, "prob_positive": 0.5},
        session={"role": "TRADER", "session_status": {"created": created}},
        role_profile={},
        portfolio_state={"OPTIONS": 1},
        engine_mode="BALANCED",
    )

    assert backend.calls[0]["session"]["created"] == created


def test_adapter_fails_closed_without_valid_timestamp():
    backend = RecordingBackendGate()
    adapter = CSSGateDashboardAdapter(backend)

    decision = adapter.approve_trade(
        candidate={"asset_class": "CRYPTO", "signal_score": 10.0, "prob_positive": 0.5},
        session={"role": "TRADER"},
        role_profile={},
        portfolio_state={"CRYPTO": 1},
        engine_mode="BALANCED",
    )

    assert decision["approved"] is False
    assert decision["reason"] == "NO_VALID_SESSION_TIMESTAMP"
    assert backend.calls == []


def test_adapter_normalizes_portfolio_keys_to_backend_shape():
    backend = RecordingBackendGate()
    adapter = CSSGateDashboardAdapter(backend)

    adapter.approve_trade(
        candidate={"asset_class": "CRYPTO", "signal_score": 10.0, "prob_positive": 0.5},
        session={"role": "TRADER", "created": time.time()},
        role_profile={},
        portfolio_state={"CRYPTO": 1, "FX": 2, "FUTURES": 0, "OPTIONS": 1},
        engine_mode="BALANCED",
    )

    assert backend.calls[0]["portfolio_state"] == {
        "crypto": 1,
        "fx": 2,
        "futures": 0,
        "options": 1,
    }


def test_adapter_returns_rich_dashboard_decision_output():
    backend = RecordingBackendGate(
        SimpleNamespace(
            approved=True,
            reason="approved: backend",
            details={"threshold": 0.58},
        )
    )
    adapter = CSSGateDashboardAdapter(backend)

    decision = adapter.approve_trade(
        candidate={"asset_class": "CRYPTO", "signal_score": 10.0, "prob_positive": 0.5},
        session={"role": "TRADER", "created": time.time()},
        role_profile={},
        portfolio_state={"CRYPTO": 1},
        engine_mode="BALANCED",
    )

    assert decision == {
        "approved": True,
        "reason": "UNIFIED_GATE_APPROVED",
        "backend_reason": "approved: backend",
        "backend_details": {"threshold": 0.58},
    }


def test_adapter_integrates_with_canonical_backend_gate():
    adapter = CSSGateDashboardAdapter(CSSUnifiedTradeGate())

    decision = adapter.approve_trade(
        candidate={"asset_class": "CRYPTO", "signal_score": 12.0, "prob_positive": 0.4},
        session={"role": "TRADER", "created": time.time()},
        role_profile={},
        portfolio_state={"CRYPTO": 0},
        engine_mode="BALANCED",
    )

    assert decision["approved"] is True
    assert decision["reason"] == "UNIFIED_GATE_APPROVED"
    assert decision["backend_details"]["asset_class"] == "crypto"


def test_dashboard_rbac_precheck_blocks_before_adapter():
    gate = RecordingDashboardGate()
    ns = _dashboard_gate_namespace(
        role_profile={"can_execute_paper_trading": False},
        gate=gate,
    )

    ok, reason = ns["approve_trade_before_register"]("CRYPTO", "BTC-USD", 12.0, 0.7)

    assert ok is False
    assert reason == "RBAC_BLOCKED_PAPER_EXECUTION"
    assert gate.calls == []
    assert ns["audit_ledger"].records[0][0] == "unified_trade_gate_reject"


def test_dashboard_session_lock_precheck_blocks_before_adapter():
    gate = RecordingDashboardGate()
    ns = _dashboard_gate_namespace(session_locked=True, gate=gate)

    ok, reason = ns["approve_trade_before_register"]("CRYPTO", "BTC-USD", 12.0, 0.7)

    assert ok is False
    assert reason == "SESSION_LOCKED_DEFENSIVE_MODE"
    assert gate.calls == []


def test_dashboard_routes_approved_trade_through_adapter():
    gate = RecordingDashboardGate()
    ns = _dashboard_gate_namespace(gate=gate)

    ok, reason = ns["approve_trade_before_register"]("CRYPTO", "BTC-USD", 12.0, 0.7)

    assert ok is True
    assert reason == "UNIFIED_GATE_APPROVED"
    assert gate.calls
    assert gate.calls[0]["portfolio_state"] == {
        "crypto": 1,
        "fx": 2,
        "futures": 0,
        "options": 1,
    }


def test_dashboard_no_longer_defines_local_css_unified_trade_gate_class():
    source = DASHBOARD_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    class_names = {
        node.name for node in tree.body if isinstance(node, ast.ClassDef)
    }

    assert "CSSUnifiedTradeGate" not in class_names
