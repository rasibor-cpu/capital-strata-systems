from engine.risk.margin_engine import (
    MarginEngine,
    MarginEscalationState,
    MarginState,
)


def test_margin_green_state():
    engine = MarginEngine()

    result = engine.calculate(
        required_margin=2000.0,
        available_margin=10000.0,
    )

    assert result.margin_utilization_pct == 20.0
    assert result.free_margin == 8000.0
    assert result.margin_state == MarginState.GREEN
    assert result.escalation_state == MarginEscalationState.NORMAL


def test_margin_yellow_state():
    engine = MarginEngine()

    result = engine.calculate(
        required_margin=5000.0,
        available_margin=10000.0,
    )

    assert result.margin_state == MarginState.YELLOW
    assert result.escalation_state == MarginEscalationState.MONITOR


def test_margin_orange_state():
    engine = MarginEngine()

    result = engine.calculate(
        required_margin=7000.0,
        available_margin=10000.0,
    )

    assert result.margin_state == MarginState.ORANGE
    assert result.escalation_state == MarginEscalationState.RESTRICT_NEW_RISK


def test_margin_red_state():
    engine = MarginEngine()

    result = engine.calculate(
        required_margin=8500.0,
        available_margin=10000.0,
    )

    assert result.margin_state == MarginState.RED
    assert result.escalation_state == MarginEscalationState.DEFENSIVE_ONLY


def test_margin_black_state():
    engine = MarginEngine()

    result = engine.calculate(
        required_margin=9500.0,
        available_margin=10000.0,
    )

    assert result.margin_state == MarginState.BLACK
    assert result.escalation_state == MarginEscalationState.CRITICAL_BLOCK


def test_margin_unknown_when_available_margin_invalid():
    engine = MarginEngine()

    result = engine.calculate(
        required_margin=1000.0,
        available_margin=0.0,
    )

    assert result.margin_state == MarginState.UNKNOWN
    assert result.escalation_state == MarginEscalationState.CRITICAL_BLOCK