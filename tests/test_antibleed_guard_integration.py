from __future__ import annotations

from typing import Any, Dict

from backend.app.risk.anti_bleed_guard import AntiBleedGuard
from engine.execution.execution_gate import ExecutionGate
from engine.risk.margin_snapshot import MarginSnapshot, MarginState


class RecordingAntiBleedGuard:
    def __init__(self, result: Dict[str, Any] | None = None) -> None:
        self.calls: list[Dict[str, Any]] = []
        self.result = result or {"approved": True, "reason": "approved"}

    def evaluate(self, **kwargs: Any) -> Dict[str, Any]:
        self.calls.append(kwargs)
        return dict(self.result)


def _valid_gate_request() -> Dict[str, Any]:
    return {
        "instrument": "EUR_USD",
        "side": "BUY",
        "notional": 100.0,
        "stop_distance_pct": 0.02,
        "equity": 10000.0,
        "equity_peak": 10000.0,
        "regime_persistence": 1.0,
        "expected_move_bps": 80.0,
        "fee_bps": 1.0,
        "spread_bps": 1.0,
        "slippage_bps": 1.0,
        "margin_snapshot": MarginSnapshot(
            broker="TEST",
            account_id="123",
            timestamp="2026-06-17T00:00:00Z",
            equity=10000.0,
            cash=10000.0,
            buying_power=5000.0,
            maintenance_margin=2500.0,
            initial_margin=5000.0,
            margin_used=0.0,
            margin_available=10000.0,
            margin_ratio=0.0,
            margin_state=MarginState.NORMAL
        ),
        "broker_mode": "PAPER",
    }


def test_antibleed_guard_is_called_in_execution_gate_path() -> None:
    guard = RecordingAntiBleedGuard()

    result = ExecutionGate(anti_bleed_guard=guard).evaluate_trade(
        **_valid_gate_request()
    )

    assert guard.calls == [
        {
            "symbol": "EUR_USD",
            "side": "BUY",
            "trade_size": 100.0,
            "expected_move_bps": 80.0,
            "fee_bps": 1.0,
            "spread_bps": 1.0,
            "slippage_bps": 1.0,
        }
    ]
    assert result["debug"]["anti_bleed_guard"]["approved"] is True


def test_valid_trade_can_proceed_when_antibleed_allows() -> None:
    result = ExecutionGate(
        anti_bleed_guard=RecordingAntiBleedGuard()
    ).evaluate_trade(**_valid_gate_request())

    assert result["decision"]["final"] == "ALLOW"
    assert result["reason"] == "approved"
    assert result["debug"]["riskgov_path"] == "validate_trade_precomputed_risk_pct"


def test_bleed_risk_candidate_is_blocked(tmp_path) -> None:
    guard = AntiBleedGuard(
        minimum_required_net_edge_bps=25.0,
        minimum_profitable_trade_size=50.0,
        cooldown_minutes=0,
        state_file=str(tmp_path / "anti_bleed_state.json"),
    )
    request = _valid_gate_request()
    request.update(
        {
            "expected_move_bps": 5.0,
            "fee_bps": 2.0,
            "spread_bps": 2.0,
            "slippage_bps": 2.0,
        }
    )

    result = ExecutionGate(anti_bleed_guard=guard).evaluate_trade(**request)

    assert result["decision"]["final"] == "BLOCK"
    assert result["reason"] == "anti_bleed_guard:expected_move_below_cost"
    assert result["debug"]["anti_bleed_guard"]["approved"] is False
    assert result["debug"]["anti_bleed_guard"]["reason"] == "expected_move_below_cost"


def test_missing_antibleed_inputs_fail_closed() -> None:
    request = _valid_gate_request()
    request.pop("expected_move_bps")

    result = ExecutionGate(
        anti_bleed_guard=RecordingAntiBleedGuard()
    ).evaluate_trade(**request)

    assert result["decision"]["final"] == "BLOCK"
    assert result["reason"] == "anti_bleed_guard:missing_anti_bleed_input:expected_move_bps"
    assert "riskgov_path" not in result["debug"]


def test_antibleed_block_reason_is_auditable() -> None:
    guard = RecordingAntiBleedGuard(
        {
            "approved": False,
            "reason": "insufficient_net_edge",
            "symbol": "EUR_USD",
            "net_edge_bps": 12.0,
            "minimum_required_net_edge_bps": 25.0,
        }
    )

    result = ExecutionGate(anti_bleed_guard=guard).evaluate_trade(
        **_valid_gate_request()
    )

    assert result["decision"]["final"] == "BLOCK"
    assert result["reason"] == "anti_bleed_guard:insufficient_net_edge"
    assert result["debug"]["anti_bleed_guard"]["symbol"] == "EUR_USD"
    assert result["debug"]["anti_bleed_guard"]["net_edge_bps"] == 12.0
    assert result["debug"]["anti_bleed_guard"]["control"] == "AntiBleedGuard"
