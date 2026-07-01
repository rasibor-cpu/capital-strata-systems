from backend.market_intelligence.multi_factor_signal_synthesizer import MultiFactorSignalSynthesizer


COMPONENTS = {
    "technical": {"status": "OK", "technical_score": 90, "technical_signal": "BULLISH", "reasons": []},
    "fundamental": {"status": "OK", "fundamental_quality_score": 10, "fundamental_signal": "NEGATIVE", "reasons": []},
    "sentiment": {"status": "OK", "sentiment_score": 50, "sentiment_signal": "NEUTRAL", "reasons": []},
    "quantitative": {"status": "OK", "alpha_score": 80, "quantitative_signal": "FAVORABLE", "reasons": []},
}


def test_multi_factor_synthesizer_uses_supplied_regime_weights() -> None:
    result = MultiFactorSignalSynthesizer().synthesize(
        **COMPONENTS,
        regime_weights={
            "status": "OK",
            "weights": {"technical": 50, "fundamental": 0, "sentiment": 0, "quantitative": 50},
            "confidence_adjustment": 5,
            "reasons": ["test_weighting"],
        },
    )

    assert result["multi_factor_score"] == 85
    assert result["regime_weights"]["technical"] == 50.0
    assert result["weighting_confidence_adjustment"] == 5
    assert "test_weighting" in result["weighting_reasons"]
    assert result["advisory_only"] is True
    assert result["execution_allowed"] is False


def test_multi_factor_synthesizer_falls_back_to_equal_weights() -> None:
    result = MultiFactorSignalSynthesizer().synthesize(**COMPONENTS)

    assert result["multi_factor_score"] == 58
    assert result["regime_weights"] == {
        "technical": 25.0,
        "fundamental": 25.0,
        "sentiment": 25.0,
        "quantitative": 25.0,
    }
    assert result["weighting_reasons"] == ["equal_weight_fallback"]
