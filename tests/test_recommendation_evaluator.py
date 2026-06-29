from __future__ import annotations

from backend.portfolio.recommendation_evaluator import RecommendationEvaluator


def test_recommendation_evaluator_scores_accurate_history() -> None:
    history = [
        {
            "recommendation": "INCREASE_RISK",
            "confidence": 0.8,
            "policy_profile": "growth",
            "market_regime": "TRENDING_UP",
            "asset_class": "equities",
            "strategy": "trend",
            "outcome": {"realized_return": 0.04, "max_drawdown": 0.02},
        },
        {
            "recommendation": "REDUCE_RISK",
            "confidence": 0.7,
            "policy_profile": "balanced",
            "market_regime": "HIGH_VOLATILITY",
            "asset_class": "crypto",
            "strategy": "momentum",
            "outcome": {"realized_return": -0.03, "max_drawdown": 0.08},
        },
        {
            "recommendation": "PAUSE_NEW_TRADES",
            "confidence": 0.6,
            "policy_profile": "balanced",
            "market_regime": "RANGING",
            "asset_class": "fx",
            "strategy": "carry",
            "outcome": {"realized_return": 0.02, "max_drawdown": 0.01},
        },
        {
            "recommendation": "MAINTAIN",
            "confidence": 0.5,
            "policy_profile": "growth",
            "market_regime": "TRENDING_UP",
            "asset_class": "equities",
            "strategy": "trend",
            "outcome": {"realized_return": -0.005, "max_drawdown": 0.01},
        },
    ]

    result = RecommendationEvaluator().evaluate(history)

    assert result["status"] == "OK"
    assert result["advisory_only"] is True
    assert result["execution_allowed"] is False
    assert result["overall_accuracy"] == 75.0
    assert result["recommendation_precision"] == 100.0
    assert result["recommendation_recall"] == 50.0
    assert result["avoided_loss"] == 0.03
    assert result["missed_opportunity"] == 0.02
    assert result["accuracy_by_policy"]["BALANCED"]["count"] == 2
    assert result["accuracy_by_asset"]["EQUITIES"]["accuracy"] == 100.0


def test_recommendation_evaluator_scores_inaccurate_history() -> None:
    history = [
        {
            "recommendation": "INCREASE_RISK",
            "confidence": 0.9,
            "policy_profile": "growth",
            "market_regime": "TRENDING_UP",
            "asset_class": "equities",
            "strategy": "trend",
            "outcome": {"realized_return": -0.04, "max_drawdown": 0.12},
        },
        {
            "recommendation": "REDUCE_RISK",
            "confidence": 0.8,
            "policy_profile": "defensive",
            "market_regime": "LOW_VOLATILITY",
            "asset_class": "fx",
            "strategy": "carry",
            "outcome": {"realized_return": 0.03, "max_drawdown": 0.01},
        },
    ]

    result = RecommendationEvaluator().evaluate(history)

    assert result["status"] == "OK"
    assert result["overall_accuracy"] == 0.0
    assert result["recommendation_effectiveness"] < 50.0
    assert "Review recommendation thresholds" in result["recommendation"]


def test_recommendation_evaluator_fails_closed_for_insufficient_history() -> None:
    result = RecommendationEvaluator().evaluate([{"recommendation": "MAINTAIN", "confidence": 0.5}])

    assert result["status"] == "DATA UNAVAILABLE"
    assert result["overall_accuracy"] is None
    assert result["advisory_only"] is True
    assert result["execution_allowed"] is False
