from backend.market_intelligence.multi_factor_signal_synthesizer import MultiFactorSignalSynthesizer


def _component(score: int, signal_key: str, signal: str) -> dict:
    return {"status": "OK", signal_key: signal, "reasons": ["test"], **{"technical_score": score}}


def test_multi_factor_signal_synthesizer_ok() -> None:
    result = MultiFactorSignalSynthesizer().synthesize(
        technical={"status": "OK", "technical_score": 70, "technical_signal": "BULLISH", "reasons": []},
        fundamental={"status": "OK", "fundamental_quality_score": 65, "fundamental_signal": "POSITIVE", "reasons": []},
        sentiment={"status": "OK", "sentiment_score": 60, "sentiment_signal": "RISK_ON", "reasons": []},
        quantitative={"status": "OK", "alpha_score": 75, "quantitative_signal": "FAVORABLE", "reasons": []},
        market_regime={"detected_regime": "RISK_ON"},
        portfolio_decision={"overall_status": "GREEN"},
    )

    assert result["status"] == "OK"
    assert result["multi_factor_signal"] in {"POSITIVE", "STRONG_POSITIVE"}
    assert result["confidence"] == 100
    assert result["advisory_only"] is True
    assert result["execution_allowed"] is False


def test_multi_factor_conflicts_reduce_confidence_and_missing_unavailable() -> None:
    conflict = MultiFactorSignalSynthesizer().synthesize(
        technical={"status": "OK", "technical_score": 80, "technical_signal": "BULLISH", "reasons": []},
        fundamental={"status": "OK", "fundamental_quality_score": 20, "fundamental_signal": "NEGATIVE", "reasons": []},
    )
    missing = MultiFactorSignalSynthesizer().synthesize()

    assert conflict["status"] == "PARTIAL"
    assert conflict["confidence"] < 100
    assert missing["status"] == "DATA UNAVAILABLE"
    assert missing["multi_factor_signal"] == "DATA_UNAVAILABLE"
