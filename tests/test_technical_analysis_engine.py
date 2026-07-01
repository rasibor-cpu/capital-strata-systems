from backend.market_intelligence.technical_analysis_engine import TechnicalAnalysisEngine


def test_technical_analysis_sufficient_data_ok() -> None:
    result = TechnicalAnalysisEngine().analyze(price_history=[100, 101, 102, 104, 106, 109], returns=[0.01, 0.02])

    assert result["status"] == "OK"
    assert result["technical_signal"] in {"BULLISH", "NEUTRAL"}
    assert 0 <= result["technical_score"] <= 100
    assert result["advisory_only"] is True
    assert result["execution_allowed"] is False


def test_technical_analysis_partial_and_missing() -> None:
    partial = TechnicalAnalysisEngine().analyze(price_history=[100, 99])
    missing = TechnicalAnalysisEngine().analyze()

    assert partial["status"] == "PARTIAL"
    assert missing["status"] == "DATA UNAVAILABLE"
    assert missing["technical_signal"] == "DATA_UNAVAILABLE"
