from __future__ import annotations

from typing import Any

from backend.app.risk.anti_bleed_guard import AntiBleedGuard
from engine.execution.execution_gate import ExecutionGate
from engine.risk.margin_snapshot import MarginSnapshot, MarginState
from engine.risk.margin_trade_gate import MarginTradeGateDecision


class RecordingMarginTradeGate:
    def __init__(self, decision: MarginTradeGateDecision | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.decision = decision or MarginTradeGateDecision(
            allowed=True,
            decision="ALLOW",
            reason="test margin allows",
            margin_state="NORMAL",
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
    margin_state: MarginState = MarginState.NORMAL,
):
    return MarginSnapshot(
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
        margin_state=margin_state
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
                margin_state=MarginState.RESTRICTED,
            ),
            broker_mode="LIVE",
        )
    )

    assert result["decision"]["final"] == "BLOCK"
    assert result["reason"].startswith("margin_trade_gate:RESTRICT_NEW_RISK")
    assert result["debug"]["margin_trade_gate"]["margin_state"] == "RESTRICTED"
    assert "riskgov_path" not in result["debug"]


def test_missing_margin_snapshot_fails_closed(tmp_path) -> None:
    result = ExecutionGate(
        anti_bleed_guard=AntiBleedGuard(
            cooldown_minutes=0,
            state_file=str(tmp_path / "anti_bleed_state.json"),
        )
    ).evaluate_trade(**_gate_request(margin_snapshot=None))

    assert result["decision"]["final"] == "BLOCK"
    assert result["reason"] == "margin_trade_gate:BLOCK:MARGIN_SNAPSHOT_UNAVAILABLE"
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
                margin_state="UNKNOWN",
            ),
            broker_mode="LIVE",
        )
    )

    assert result["decision"]["final"] == "BLOCK"
    assert result["reason"].startswith("margin_trade_gate:BLOCK:invalid_snapshot")
    assert result["debug"]["margin_trade_gate"]["margin_state"] == "UNKNOWN"


def test_margin_block_reason_is_auditable(tmp_path) -> None:
    margin_gate = RecordingMarginTradeGate(
        MarginTradeGateDecision(
            allowed=False,
            decision="RESTRICT_NEW_RISK",
            reason="test margin restricted block",
            margin_state="RESTRICTED",
            escalation_state="UNKNOWN",
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
    assert result["reason"] == "margin_trade_gate:RESTRICT_NEW_RISK:test margin restricted block"
    assert result["debug"]["margin_trade_gate"] == {
        "allowed": False,
        "decision": "RESTRICT_NEW_RISK",
        "reason": "test margin restricted block",
        "margin_state": "RESTRICTED",
        "escalation_state": "UNKNOWN",
        "margin_utilization_pct": 85.0,
        "control": "MarginTradeGate",
    }
