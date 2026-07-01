from backend.market_intelligence.sentiment_intelligence_engine import SentimentIntelligenceEngine


def test_sentiment_intelligence_internal_positive_negative() -> None:
    result = SentimentIntelligenceEngine().analyze(
        alerts=[{"severity": "INFO", "message": "GREEN runtime READY"}],
        recommendation_history=[{"portfolio_recommendation": "MAINTAIN"}],
        market_regime="RISK_ON",
    )

    assert result["status"] == "OK"
    assert result["sentiment_signal"] == "RISK_ON"
    assert result["advisory_only"] is True
    assert result["execution_allowed"] is False


def test_sentiment_intelligence_missing_data_unavailable() -> None:
    result = SentimentIntelligenceEngine().analyze()

    assert result["status"] == "DATA UNAVAILABLE"
    assert result["sentiment_signal"] == "DATA_UNAVAILABLE"
