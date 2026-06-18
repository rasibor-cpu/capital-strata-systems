import pytest
from engine.risk.margin_trade_gate import MarginTradeGate, MarginTradeGateDecision
from engine.risk.margin_snapshot import MarginSnapshot, MarginState

def _build_snapshot(buying_power=5000.0, margin_state=MarginState.NORMAL):
    return MarginSnapshot(
        broker="TEST",
        account_id="123",
        timestamp="2026-06-17T00:00:00Z",
        equity=10000.0,
        cash=10000.0,
        buying_power=buying_power,
        maintenance_margin=2500.0,
        initial_margin=5000.0,
        margin_used=5000.0,
        margin_available=5000.0,
        margin_ratio=0.5,
        margin_state=margin_state
    )

def test_margin_gate_normal_allows_progression():
    gate = MarginTradeGate()
    snap = _build_snapshot(margin_state=MarginState.NORMAL)
    decision = gate.evaluate(snap)
    assert decision.allowed is True
    assert decision.decision == "ALLOW"

def test_margin_gate_warning_allows_progression():
    gate = MarginTradeGate()
    snap = _build_snapshot(margin_state=MarginState.WARNING)
    decision = gate.evaluate(snap)
    assert decision.allowed is True
    assert decision.decision == "ALLOW_WITH_WARNING"

def test_margin_gate_restricted_blocks_new_risk():
    gate = MarginTradeGate()
    snap = _build_snapshot(margin_state=MarginState.RESTRICTED)
    decision = gate.evaluate(snap)
    assert decision.allowed is False
    assert decision.decision == "RESTRICT_NEW_RISK"

def test_margin_gate_critical_blocks_new_risk():
    gate = MarginTradeGate()
    snap = _build_snapshot(margin_state=MarginState.CRITICAL)
    decision = gate.evaluate(snap)
    assert decision.allowed is False
    assert decision.decision == "RESTRICT_NEW_RISK"

def test_margin_gate_liquidation_risk_blocks():
    gate = MarginTradeGate()
    snap = _build_snapshot(margin_state=MarginState.LIQUIDATION_RISK)
    decision = gate.evaluate(snap)
    assert decision.allowed is False
    assert decision.decision == "BLOCK"
    assert decision.reason == "liquidation_risk"

def test_margin_gate_missing_snapshot_blocks():
    gate = MarginTradeGate()
    decision = gate.evaluate(None)
    assert decision.allowed is False
    assert decision.decision == "BLOCK"
    assert decision.reason == "MARGIN_SNAPSHOT_UNAVAILABLE"

def test_margin_gate_invalid_snapshot_blocks():
    gate = MarginTradeGate()
    # Missing buying_power
    class InvalidSnap:
        pass
    decision = gate.evaluate(InvalidSnap())
    assert decision.allowed is False
    assert decision.decision == "BLOCK"
    assert decision.reason == "MARGIN_SNAPSHOT_UNAVAILABLE"

    # Invalid buying_power type
    snap = _build_snapshot(buying_power="invalid_string")
    decision = gate.evaluate(snap)
    assert decision.allowed is False
    assert decision.decision == "BLOCK"
    assert decision.reason == "invalid_snapshot"

def test_margin_gate_negative_buying_power():
    gate = MarginTradeGate()
    snap = _build_snapshot(buying_power=-100.0)
    decision = gate.evaluate(snap)
    assert decision.allowed is False
    assert decision.decision == "BLOCK"
    assert decision.reason == "negative_buying_power"

def test_gate_returns_canonical_decision_object():
    gate = MarginTradeGate()
    snap = _build_snapshot()
    decision = gate.evaluate(snap)
    assert isinstance(decision, MarginTradeGateDecision)
    assert isinstance(decision.allowed, bool)
    assert isinstance(decision.decision, str)
    assert isinstance(decision.reason, str)
    assert isinstance(decision.margin_state, str)
    assert isinstance(decision.escalation_state, str)
    assert isinstance(decision.margin_utilization_pct, float)
