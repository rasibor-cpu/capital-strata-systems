from __future__ import annotations

from backend.analytics.adaptive_threshold_calibration_engine import AdaptiveThresholdCalibrationEngine


def test_threshold_calibration_recommendations() -> None:
    engine = AdaptiveThresholdCalibrationEngine()
    result = engine.recommend([
        {"strategy_id": "alpha", "asset_class": "EQUITY", "market_regime": "TREND", "confidence": 0.8, "quality_score": 84.0, "realized_pnl": 8.0},
        {"strategy_id": "alpha", "asset_class": "EQUITY", "market_regime": "TREND", "confidence": 0.7, "quality_score": 72.0, "realized_pnl": 4.0},
        {"strategy_id": "beta", "asset_class": "FX", "market_regime": "VOLATILE", "confidence": 0.5, "quality_score": 45.0, "realized_pnl": -2.0},
    ])

    assert result["metadata"]["trade_count"] == 3
    assert len(result["strategy_thresholds"]) == 2
    assert result["strategy_thresholds"][0]["strategy_id"] == "alpha"
    assert 0.0 <= result["strategy_thresholds"][0]["entry_threshold"] <= 1.0


def test_threshold_calibration_empty() -> None:
    result = AdaptiveThresholdCalibrationEngine().recommend([])
    assert result["strategy_thresholds"] == []
    assert result["metadata"]["trade_count"] == 0
