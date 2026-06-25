from __future__ import annotations

import pytest

from backend.analytics.performance_analytics_engine import PerformanceAnalyticsEngine, PerformanceAnalyticsEngineError


def _trade(trade_id, pnl, quality_score, asset_class="EQUITY", strategy_id="alpha", regime="TRENDING", closed=True, hold=30.0):
    return {
        "trade_id": trade_id,
        "symbol": "AAPL",
        "asset_class": asset_class,
        "strategy_id": strategy_id,
        "market_regime": regime,
        "realized_pnl": pnl,
        "entry_price": 100.0,
        "exit_price": 101.0,
        "quantity": 10.0,
        "holding_duration_minutes": hold,
        "is_closed": closed,
        "quality_score": quality_score,
    }


def test_positive_performance_metrics() -> None:
    engine = PerformanceAnalyticsEngine()
    metrics = engine.analyze([
        _trade("t1", 10.0, 88.0),
        _trade("t2", 5.0, 72.0, strategy_id="beta", regime="RANGING"),
        _trade("t3", -2.0, 48.0),
    ])

    assert metrics["win_rate"] > 0.6
    assert metrics["profit_factor"] > 1.0
    assert metrics["expectancy"] > 0.0
    assert metrics["asset_performance"]["EQUITY"]["trade_count"] == 3


def test_losing_performance_metrics() -> None:
    engine = PerformanceAnalyticsEngine()
    metrics = engine.analyze([
        _trade("t1", -5.0, 35.0),
        _trade("t2", -10.0, 32.0),
    ])

    assert metrics["win_rate"] == 0.0
    assert metrics["profit_factor"] == 0.0
    assert metrics["trade_quality_distribution"]["E"] == 2


def test_empty_metrics() -> None:
    engine = PerformanceAnalyticsEngine()
    metrics = engine.analyze([])

    assert metrics["trade_count"] == 0
    assert metrics["win_rate"] == 0.0


def test_invalid_inputs_fail_closed() -> None:
    engine = PerformanceAnalyticsEngine()
    with pytest.raises(PerformanceAnalyticsEngineError):
        engine.analyze(None)
