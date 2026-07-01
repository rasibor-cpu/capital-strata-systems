from backend.learning.regime_learning import RegimeLearningEngine


def test_regime_learning_groups_performance_by_regime() -> None:
    result = RegimeLearningEngine().analyze(
        [
            {"market_regime": "TRENDING_UP", "factor_scores": {"technical": 85, "quantitative": 80}, "realized_return": 5.0},
            {"market_regime": "RISK_OFF", "factor_scores": {"technical": 70, "sentiment": 20}, "realized_return": -3.0},
        ]
    )

    assert result["status"] == "OK"
    assert "TRENDING_UP" in result["regimes"]
    assert result["strongest_regime"] == "TRENDING_UP"
    assert result["advisory_only"] is True


def test_regime_learning_missing_history_fails_closed() -> None:
    result = RegimeLearningEngine().analyze([])

    assert result["status"] == "DATA UNAVAILABLE"
    assert result["weakest_regime"] == "DATA UNAVAILABLE"
