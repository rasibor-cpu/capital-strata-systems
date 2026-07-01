from backend.market_intelligence.fundamental_analysis_engine import FundamentalAnalysisEngine


def test_fundamental_analysis_scores_internal_metadata() -> None:
    result = FundamentalAnalysisEngine().evaluate(
        {"symbol": "AAPL", "asset_class": "EQUITY", "valuation_score": 72, "balance_quality": 80}
    )

    assert result["status"] == "OK"
    assert result["fundamental_signal"] == "POSITIVE"
    assert result["valuation_status"] == "ATTRACTIVE"
    assert result["advisory_only"] is True
    assert result["execution_allowed"] is False


def test_fundamental_analysis_partial_and_missing() -> None:
    partial = FundamentalAnalysisEngine().evaluate({"symbol": "BTC-USD", "asset_class": "CRYPTO"})
    missing = FundamentalAnalysisEngine().evaluate({})

    assert partial["status"] == "PARTIAL"
    assert partial["fundamental_signal"] == "NEUTRAL"
    assert missing["status"] == "DATA UNAVAILABLE"
    assert missing["fundamental_signal"] == "DATA_UNAVAILABLE"
