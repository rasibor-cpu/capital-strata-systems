import pytest

from engine.risk.portfolio_var_engine import (
    PortfolioVaREngine,
)


def test_var_calculation():
    engine = PortfolioVaREngine()

    result = engine.calculate_var(
        portfolio_value=100000.0,
        returns=[
            0.01,
            -0.01,
            0.02,
            -0.015,
            0.005,
            -0.007,
        ],
        confidence_level=0.95,
    )

    assert result.portfolio_value == 100000.0
    assert result.one_day_var > 0


def test_invalid_confidence():
    engine = PortfolioVaREngine()

    with pytest.raises(ValueError):
        engine.calculate_var(
            portfolio_value=100000.0,
            returns=[0.01, -0.01],
            confidence_level=0.975,
        )


def test_insufficient_returns():
    engine = PortfolioVaREngine()

    with pytest.raises(ValueError):
        engine.calculate_var(
            portfolio_value=100000.0,
            returns=[0.01],
        )