import pytest

from backend.analytics import AdaptivePositionSizingEngine, AdaptivePositionSizingError


def test_successful_sizing():
    engine = AdaptivePositionSizingEngine()
    allocations = [
        {
            "symbol": "AAPL",
            "allocation_weight": 0.6,
            "allocation_amount": 600.0,
            "status": "PREFERRED",
        }
    ]

    sized = engine.size_positions(
        allocations,
        available_capital=1000.0,
        confidence=0.8,
        maximum_risk_percentage=0.2,
        minimum_trade_size=10.0,
        maximum_trade_size=150.0,
    )

    assert sized[0]["symbol"] == "AAPL"
    assert sized[0]["recommended_capital"] == pytest.approx(120.0)
    assert sized[0]["recommended_position_size"] == pytest.approx(120.0)
    assert sized[0]["sizing_status"] == "APPROVED"


def test_confidence_adjustment():
    engine = AdaptivePositionSizingEngine()
    allocations = [{"symbol": "MSFT", "allocation_weight": 0.4, "allocation_amount": 400.0, "status": "PREFERRED"}]

    sized = engine.size_positions(
        allocations,
        available_capital=1000.0,
        confidence=0.5,
        maximum_risk_percentage=0.2,
        minimum_trade_size=10.0,
        maximum_trade_size=200.0,
    )

    assert sized[0]["recommended_capital"] == pytest.approx(40.0)


def test_max_risk_enforcement():
    engine = AdaptivePositionSizingEngine()
    allocations = [{"symbol": "TSLA", "allocation_weight": 1.0, "allocation_amount": 1000.0, "status": "PREFERRED"}]

    sized = engine.size_positions(
        allocations,
        available_capital=1000.0,
        confidence=1.0,
        maximum_risk_percentage=0.1,
        minimum_trade_size=10.0,
        maximum_trade_size=500.0,
    )

    assert sized[0]["recommended_capital"] == pytest.approx(100.0)
    assert sized[0]["recommended_position_size"] == pytest.approx(100.0)


def test_invalid_input():
    engine = AdaptivePositionSizingEngine()

    with pytest.raises(AdaptivePositionSizingError):
        engine.size_positions(
            [{"symbol": "AAPL", "allocation_weight": 0.5, "allocation_amount": 100.0, "status": "PREFERRED"}],
            available_capital=-1.0,
            confidence=0.8,
            maximum_risk_percentage=0.2,
            minimum_trade_size=10.0,
            maximum_trade_size=100.0,
        )

    with pytest.raises(AdaptivePositionSizingError):
        engine.size_positions(
            [{"symbol": "AAPL", "allocation_weight": 0.5, "allocation_amount": 100.0, "status": "PREFERRED"}],
            available_capital=100.0,
            confidence=1.2,
            maximum_risk_percentage=0.2,
            minimum_trade_size=10.0,
            maximum_trade_size=100.0,
        )
