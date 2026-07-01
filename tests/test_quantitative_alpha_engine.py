from backend.market_intelligence.quantitative_alpha_engine import QuantitativeAlphaEngine


def test_quantitative_alpha_sufficient_data_ok() -> None:
    result = QuantitativeAlphaEngine().evaluate(
        returns=[0.01, 0.02, -0.005, 0.015, 0.01],
        win_loss_history=[1, 1, -1, 1],
        asset_class_pnl={"CRYPTO": 2.5},
        volatility=0.02,
        drawdown=0.01,
        trend_stability=0.8,
    )

    assert result["status"] == "OK"
    assert result["quantitative_signal"] in {"FAVORABLE", "NEUTRAL"}
    assert 0 <= result["alpha_score"] <= 100
    assert result["advisory_only"] is True
    assert result["execution_allowed"] is False


def test_quantitative_alpha_missing_data_unavailable() -> None:
    result = QuantitativeAlphaEngine().evaluate()

    assert result["status"] == "DATA UNAVAILABLE"
    assert result["quantitative_signal"] == "DATA_UNAVAILABLE"
