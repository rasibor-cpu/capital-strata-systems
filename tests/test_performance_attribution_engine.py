from __future__ import annotations

from backend.analytics.performance_attribution_engine import PerformanceAttributionEngine


def test_attribution_by_dimensions() -> None:
    engine = PerformanceAttributionEngine()
    result = engine.attribute([
        {"trade_id": "t1", "strategy_id": "alpha", "asset_class": "EQUITY", "market_regime": "TRENDING", "timestamp_close": "2026-06-24T14:30:00+00:00", "holding_time_seconds": 600.0, "confidence": 0.9, "quality_score": 88.0, "exit_reason": "take_profit", "position_size": 1200.0, "realized_pnl": 10.0},
        {"trade_id": "t2", "strategy_id": "alpha", "asset_class": "EQUITY", "market_regime": "RANGING", "timestamp_close": "2026-06-24T15:30:00+00:00", "holding_time_seconds": 7200.0, "confidence": 0.4, "quality_score": 44.0, "exit_reason": "stop_loss", "position_size": 4000.0, "realized_pnl": -4.0},
    ])

    assert result["strategy"][0]["strategy_id"] == "alpha"
    assert result["asset_class"][0]["asset_class"] == "EQUITY"
    assert result["market_regime"][0]["market_regime"] == "RANGING"
    assert result["day_of_week"][0]["day_of_week"] == "Wednesday"
    assert result["hour_of_day"][0]["hour_of_day"] == "14"
    assert result["trade_duration_bucket"][0]["trade_duration_bucket"] == "0-15m"
    assert result["confidence_bucket"][0]["confidence_bucket"] == "25-50%"
    assert result["trade_quality_bucket"][0]["trade_quality_bucket"] == "A"
    assert result["exit_reason"][0]["exit_reason"] == "stop_loss"
    assert result["position_size_bucket"][0]["position_size_bucket"] == "1k-5k"
