from engine.risk.margin_engine import (
    MarginEngine,
    MarginEscalationState,
    MarginSnapshot,
    MarginState,
)
from engine.risk.margin_trade_gate import (
    MarginTradeGate,
    MarginTradeGateDecision,
)


def _snapshot(required_margin: float, available_margin: float, margin_source: str = "LIVE"):
    return MarginEngine().calculate(
        required_margin=required_margin,
        available_margin=available_margin,
        margin_source=margin_source,
    )


def test_green_allows():
    decision = MarginTradeGate().evaluate(
        _snapshot(required_margin=2000.0, available_margin=10000.0),
        broker_mode="LIVE",
    )

    assert decision.allowed is True
    assert decision.decision == "ALLOW"
    assert decision.margin_state == "GREEN"
    assert decision.escalation_state == "NORMAL"


def test_yellow_monitors_but_allows():
    decision = MarginTradeGate().evaluate(
        _snapshot(required_margin=5000.0, available_margin=10000.0),
        broker_mode="LIVE",
    )

    assert decision.allowed is True
    assert decision.decision == "MONITOR"
    assert decision.margin_state == "YELLOW"
    assert decision.escalation_state == "MONITOR"


def test_orange_restricts_new_risk():
    decision = MarginTradeGate().evaluate(
        _snapshot(required_margin=7000.0, available_margin=10000.0),
        broker_mode="PAPER",
    )

    assert decision.allowed is False
    assert decision.decision == "RESTRICT_NEW_RISK"
    assert decision.margin_state == "ORANGE"


def test_red_defensive_only():
    decision = MarginTradeGate().evaluate(
        _snapshot(required_margin=8500.0, available_margin=10000.0),
        broker_mode="PAPER",
    )

    assert decision.allowed is False
    assert decision.decision == "DEFENSIVE_ONLY"
    assert decision.margin_state == "RED"


def test_black_blocks():
    decision = MarginTradeGate().evaluate(
        _snapshot(required_margin=9500.0, available_margin=10000.0),
        broker_mode="PAPER",
    )

    assert decision.allowed is False
    assert decision.decision == "BLOCK"
    assert decision.margin_state == "BLACK"


def test_unknown_blocks():
    decision = MarginTradeGate().evaluate(
        _snapshot(required_margin=1000.0, available_margin=0.0),
        broker_mode="PAPER",
    )

    assert decision.allowed is False
    assert decision.decision == "BLOCK"
    assert decision.margin_state == "UNKNOWN"


def test_live_unknown_fails_closed():
    snapshot = MarginSnapshot(
        margin_source="LIVE",
        required_margin=0.0,
        available_margin=0.0,
        free_margin=0.0,
        margin_utilization_pct=0.0,
        margin_state=MarginState.UNKNOWN,
        escalation_state=MarginEscalationState.CRITICAL_BLOCK,
    )

    decision = MarginTradeGate().evaluate(snapshot, broker_mode="LIVE")

    assert decision.allowed is False
    assert decision.decision == "BLOCK"
    assert "Fail-closed" in decision.reason


def test_paper_simulated_green_allows():
    decision = MarginTradeGate().evaluate(
        _snapshot(
            required_margin=1000.0,
            available_margin=10000.0,
            margin_source="SIMULATED",
        ),
        broker_mode="PAPER",
    )

    assert decision.allowed is True
    assert decision.decision == "ALLOW"
    assert "PAPER simulated" in decision.reason


def test_gate_returns_canonical_decision_object():
    decision = MarginTradeGate().evaluate(
        _snapshot(required_margin=2000.0, available_margin=10000.0),
        broker_mode="LIVE",
    )

    assert isinstance(decision, MarginTradeGateDecision)
    assert isinstance(decision.allowed, bool)
    assert isinstance(decision.decision, str)
    assert isinstance(decision.reason, str)
    assert isinstance(decision.margin_state, str)
    assert isinstance(decision.escalation_state, str)
    assert isinstance(decision.margin_utilization_pct, float)
