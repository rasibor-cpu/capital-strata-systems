from __future__ import annotations

from backend.analytics.optimization_validation_engine import OptimizationValidationEngine


def test_optimization_validation_safe_review_reject() -> None:
    package = {
        "confidence_score": 0.75,
        "recommended_threshold_changes": {"strategy_thresholds": []},
        "recommended_sizing_changes": [{"strategy_id": "alpha", "action": "KEEP"}],
        "recommended_strategy_changes": [{"strategy_id": "alpha", "recommendation": "PROMOTE"}],
        "recommended_regime_changes": {"TREND": {"confidence_threshold": 0.6}},
    }
    backtest = {
        "baseline_expectancy": 1.0,
        "optimized_expectancy": 1.1,
        "baseline_drawdown": 3.0,
        "optimized_drawdown": 2.8,
        "backtest_decision": "ACCEPT",
    }
    result = OptimizationValidationEngine().validate(package, backtest)

    assert result["summary"]["REJECT"] == 0
    assert result["overall"] in {"SAFE", "REVIEW"}
