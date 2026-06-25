from __future__ import annotations

import pytest

from backend.analytics.adaptive_calibration_engine import AdaptiveCalibrationEngine, AdaptiveCalibrationEngineError


def test_bounded_calibration() -> None:
    engine = AdaptiveCalibrationEngine()
    result = engine.recommend(
        {
            "win_rate": 0.7,
            "profit_factor": 1.5,
            "max_drawdown": 0.1,
            "recovery_factor": 0.4,
            "consecutive_losses": 1,
            "concentration_score": 0.2,
            "strategy_strength": 0.6,
            "regime_strength": 0.5,
        },
        calibration_state={
            "trade_quality_weights": [0.12] * 8,
            "strategy_weighting": [0.1] * 6,
            "regime_sensitivity": [1.0] * 7,
        },
    )

    assert 0.0 <= result["acceptance_threshold"] <= 100.0
    assert 0.25 <= result["position_sizing_multiplier"] <= 1.5
    assert set(result["trade_quality_weights"]) == {
        "adaptive_exit_quality",
        "capital_allocation",
        "market_regime",
        "portfolio_concentration",
        "position_sizing",
        "replay_confidence",
        "risk_reward",
        "strategy_intelligence",
    }


def test_calibration_audit_trail() -> None:
    engine = AdaptiveCalibrationEngine()
    result = engine.recommend({"win_rate": 0.2, "profit_factor": 0.8, "max_drawdown": 0.3, "recovery_factor": 0.1, "consecutive_losses": 3, "concentration_score": 0.4, "strategy_strength": 0.3, "regime_strength": 0.4})

    assert isinstance(result["audit_trail"], list)
    assert any(entry["field"] == "win_rate" for entry in result["audit_trail"])
    assert any(entry["field"] == "max_drawdown" for entry in result["audit_trail"])


def test_invalid_input_fail_closed() -> None:
    engine = AdaptiveCalibrationEngine()
    with pytest.raises(AdaptiveCalibrationEngineError):
        engine.recommend("bad")


def test_empty_current_values_fail_closed() -> None:
    engine = AdaptiveCalibrationEngine()
    result = engine.recommend({"win_rate": 0.4, "profit_factor": 0.9, "max_drawdown": 0.1, "recovery_factor": 0.1, "consecutive_losses": 0, "concentration_score": 0.2, "strategy_strength": 0.5, "regime_strength": 0.5}, calibration_state={"trade_quality_weights": []})

    assert result["exit_confidence"] >= 0.0
