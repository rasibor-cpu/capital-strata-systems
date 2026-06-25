from __future__ import annotations

import pytest

from backend.analytics.dynamic_acceptance_engine import (
    DynamicAcceptanceEngine,
    DynamicAcceptanceEngineError,
)


def test_threshold_adjustment() -> None:
    engine = DynamicAcceptanceEngine()
    result = engine.resolve_threshold(
        market_regime="TRENDING",
        volatility=0.2,
        drawdown=-0.1,
        recent_performance=0.3,
        concentration_risk=0.2,
    )

    assert 0.0 <= result["threshold"] <= 100.0


def test_drawdown_raises_threshold() -> None:
    engine = DynamicAcceptanceEngine()
    base = engine.resolve_threshold(
        market_regime="TRENDING",
        volatility=0.2,
        drawdown=0.0,
        recent_performance=0.1,
        concentration_risk=0.2,
    )
    stressed = engine.resolve_threshold(
        market_regime="TRENDING",
        volatility=0.2,
        drawdown=-0.3,
        recent_performance=0.1,
        concentration_risk=0.2,
    )

    assert stressed["threshold"] > base["threshold"]


def test_concentration_risk_raises_threshold() -> None:
    engine = DynamicAcceptanceEngine()
    low = engine.resolve_threshold(
        market_regime="RANGING",
        volatility=0.2,
        drawdown=-0.05,
        recent_performance=0.0,
        concentration_risk=0.1,
    )
    high = engine.resolve_threshold(
        market_regime="RANGING",
        volatility=0.2,
        drawdown=-0.05,
        recent_performance=0.0,
        concentration_risk=0.8,
    )

    assert high["threshold"] > low["threshold"]


def test_invalid_inputs_fail_closed() -> None:
    engine = DynamicAcceptanceEngine()
    with pytest.raises(DynamicAcceptanceEngineError):
        engine.resolve_threshold(
            market_regime="",
            volatility=0.1,
            drawdown=0.0,
            recent_performance=0.0,
            concentration_risk=0.1,
        )

    with pytest.raises(DynamicAcceptanceEngineError):
        engine.resolve_threshold(
            market_regime="TRENDING",
            volatility=1.2,
            drawdown=0.0,
            recent_performance=0.0,
            concentration_risk=0.1,
        )
