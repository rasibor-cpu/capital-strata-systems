from __future__ import annotations

from typing import Any

from backend.app.risk.anti_bleed_guard import AntiBleedGuard
from engine.execution.execution_gate import ExecutionGate
from engine.risk.margin_engine import MarginEngine
from engine.risk.margin_trade_gate import MarginTradeGateDecision


class RecordingMarginTradeGate:
    def __init__(self, decision: MarginTradeGateDecision | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.decision = decision or MarginTradeGateDecision(
            allowed=True,
            decision="ALLOW",
            reason="test margin allows",
            margin_state="GREEN",
            escalation_state="NORMAL",
            margin_utilization_pct=10.0,
        )

    def evaluate(self, margin_snapshot: Any, *, broker_mode: str = "PAPER") -> MarginTradeGateDecision:
        self.calls.append(
            {
                "margin_snapshot": margin_snapshot,
                "broker_mode": broker_mode,
            }
        )
        return self.decision


def _margin_snapshot(
    *,
    required_margin: float = 0.0,
    available_margin: float = 10000.0,
    margin_source: str = "SIMULATED",
):
    return MarginEngine().calculate(
        required_margin=required_margin,
        available_margin=available_margin,
        margin_source=margin_source,
    )


def _gate_request(**overrides: Any) -> dict[str, Any]:
    request = {
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
        "margin_snapshot": _margin_snapshot(),
        "broker_mode": "PAPER",
    }
    request.update(overrides)
    return request


def test_margin_trade_gate_is_called_in_execution_gate_path(tmp_path) -> None:
    margin_gate = RecordingMarginTradeGate()
    snapshot = _margin_snapshot()

    result = ExecutionGate(
        anti_bleed_guard=AntiBleedGuard(
            cooldown_minutes=0,
            state_file=str(tmp_path / "anti_bleed_state.json"),
        ),
        margin_trade_gate=margin_gate,
    ).evaluate_trade(**_gate_request(margin_snapshot=snapshot))

    assert result["decision"]["final"] == "ALLOW"
    assert margin_gate.calls == [
        {
            "margin_snapshot": snapshot,
            "broker_mode": "PAPER",
        }
    ]
    assert result["debug"]["margin_trade_gate"]["control"] == "MarginTradeGate"


def test_margin_green_allows_execution_gate_to_continue(tmp_path) -> None:
    result = ExecutionGate(
        anti_bleed_guard=AntiBleedGuard(
            cooldown_minutes=0,
            state_file=str(tmp_path / "anti_bleed_state.json"),
        )
    ).evaluate_trade(**_gate_request())

    assert result["decision"]["final"] == "ALLOW"
    assert result["reason"] == "approved"
    assert result["debug"]["margin_trade_gate"]["allowed"] is True
    assert result["debug"]["riskgov_path"] == "validate_trade_precomputed_risk_pct"


def test_margin_orange_blocks_before_risk_governor(tmp_path) -> None:
    result = ExecutionGate(
        anti_bleed_guard=AntiBleedGuard(
            cooldown_minutes=0,
            state_file=str(tmp_path / "anti_bleed_state.json"),
        )
    ).evaluate_trade(
        **_gate_request(
            margin_snapshot=_margin_snapshot(
                required_margin=7000.0,
                available_margin=10000.0,
                margin_source="LIVE",
            ),
            broker_mode="LIVE",
        )
    )

    assert result["decision"]["final"] == "BLOCK"
    assert result["reason"].startswith("margin_trade_gate:RESTRICT_NEW_RISK")
    assert result["debug"]["margin_trade_gate"]["margin_state"] == "ORANGE"
    assert result["debug"]["margin_trade_gate"]["escalation_state"] == "RESTRICT_NEW_RISK"
    assert "riskgov_path" not in result["debug"]


def test_missing_margin_snapshot_fails_closed(tmp_path) -> None:
    result = ExecutionGate(
        anti_bleed_guard=AntiBleedGuard(
            cooldown_minutes=0,
            state_file=str(tmp_path / "anti_bleed_state.json"),
        )
    ).evaluate_trade(**_gate_request(margin_snapshot=None))

    assert result["decision"]["final"] == "BLOCK"
    assert result["reason"] == "margin_trade_gate:BLOCK:missing_margin_snapshot"
    assert result["debug"]["margin_trade_gate"]["control"] == "MarginTradeGate"
    assert "riskgov_path" not in result["debug"]


def test_live_unknown_margin_state_fails_closed(tmp_path) -> None:
    result = ExecutionGate(
        anti_bleed_guard=AntiBleedGuard(
            cooldown_minutes=0,
            state_file=str(tmp_path / "anti_bleed_state.json"),
        )
    ).evaluate_trade(
        **_gate_request(
            margin_snapshot=_margin_snapshot(
                required_margin=1000.0,
                available_margin=0.0,
                margin_source="LIVE",
            ),
            broker_mode="LIVE",
        )
    )

    assert result["decision"]["final"] == "BLOCK"
    assert result["reason"].startswith("margin_trade_gate:BLOCK:Fail-closed")
    assert result["debug"]["margin_trade_gate"]["margin_state"] == "UNKNOWN"


def test_margin_block_reason_is_auditable(tmp_path) -> None:
    margin_gate = RecordingMarginTradeGate(
        MarginTradeGateDecision(
            allowed=False,
            decision="DEFENSIVE_ONLY",
            reason="test margin defensive-only block",
            margin_state="RED",
            escalation_state="DEFENSIVE_ONLY",
            margin_utilization_pct=85.0,
        )
    )

    result = ExecutionGate(
        anti_bleed_guard=AntiBleedGuard(
            cooldown_minutes=0,
            state_file=str(tmp_path / "anti_bleed_state.json"),
        ),
        margin_trade_gate=margin_gate,
    ).evaluate_trade(**_gate_request())

    assert result["decision"]["final"] == "BLOCK"
    assert result["reason"] == "margin_trade_gate:DEFENSIVE_ONLY:test margin defensive-only block"
    assert result["debug"]["margin_trade_gate"] == {
        "allowed": False,
        "decision": "DEFENSIVE_ONLY",
        "reason": "test margin defensive-only block",
        "margin_state": "RED",
        "escalation_state": "DEFENSIVE_ONLY",
        "margin_utilization_pct": 85.0,
        "control": "MarginTradeGate",
    }
