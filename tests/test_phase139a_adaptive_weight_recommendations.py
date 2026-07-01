from backend.learning.adaptive_weight_recommendations import AdaptiveWeightRecommendationEngine


def test_adaptive_weight_recommendations_normalize_to_100() -> None:
    result = AdaptiveWeightRecommendationEngine().recommend(
        factor_performance={
            "status": "OK",
            "factors": {
                "technical": {"sample_size": 10, "reliability_score": 90, "hit_rate": 90, "average_outcome": 3},
                "fundamental": {"sample_size": 10, "reliability_score": 40, "hit_rate": 40, "average_outcome": -1},
                "sentiment": {"sample_size": 10, "reliability_score": 60, "hit_rate": 60, "average_outcome": 1},
                "quantitative": {"sample_size": 10, "reliability_score": 80, "hit_rate": 80, "average_outcome": 2},
            },
        },
        current_weights={"technical": 25, "fundamental": 25, "sentiment": 25, "quantitative": 25},
    )

    assert result["status"] == "OK"
    assert round(sum(result["recommended_weights"].values()), 6) == 100.0
    assert result["recommended_weights"]["technical"] > result["recommended_weights"]["fundamental"]
    assert result["execution_allowed"] is False


def test_adaptive_weight_recommendations_balanced_on_insufficient_evidence() -> None:
    result = AdaptiveWeightRecommendationEngine().recommend(factor_performance={"status": "DATA UNAVAILABLE", "factors": {}})

    assert round(sum(result["recommended_weights"].values()), 6) == 100.0
    assert "balanced_default_due_to_insufficient_learning" in result["reasons"]
