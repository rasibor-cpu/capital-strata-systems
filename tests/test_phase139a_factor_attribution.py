from backend.learning.factor_attribution import FactorAttributionEngine


def test_factor_attribution_uses_weights_and_outcomes() -> None:
    result = FactorAttributionEngine().attribute(
        [
            {
                "factor_scores": {"technical": 80, "fundamental": 20, "sentiment": 50, "quantitative": 70},
                "regime_weights": {"technical": 50, "fundamental": 10, "sentiment": 10, "quantitative": 30},
                "realized_return": 10.0,
            }
        ]
    )

    assert result["status"] == "OK"
    assert result["dominant_factor"] == "technical"
    assert result["factor_attribution"]["technical"]["total_contribution"] > 0
    assert result["advisory_only"] is True
    assert result["execution_allowed"] is False


def test_factor_attribution_missing_history_fails_closed() -> None:
    result = FactorAttributionEngine().attribute(None)

    assert result["status"] == "DATA UNAVAILABLE"
    assert result["total_attributed_return"] == 0.0
