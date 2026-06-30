from __future__ import annotations

from backend.portfolio.runtime_exposure_builder import RuntimeExposureBuilder


def test_runtime_exposure_builder_marks_startup_with_zero_positions_limited() -> None:
    result = RuntimeExposureBuilder().build([])

    assert result["status"] == "LIMITED"
    assert result["portfolio_state"] == "NO_PORTFOLIO"
    assert result["total_exposure"] == 0.0
    assert result["asset_class_exposure"] == {}
    assert result["symbol_exposure"] == {}
    assert result["execution_allowed"] is False
    assert "No current exposure." in result["reasons"]


def test_runtime_exposure_builder_calculates_active_exposure_views() -> None:
    result = RuntimeExposureBuilder().build(
        [
            {
                "symbol": "SPY",
                "asset_class": "EQUITIES",
                "sector": "ETF",
                "strategy_id": "trend",
                "market_value": 60000.0,
            },
            {
                "symbol": "BTC-USD",
                "asset_class": "CRYPTO",
                "sector": "DIGITAL",
                "strategy_id": "momentum",
                "market_value": 40000.0,
            },
        ]
    )

    assert result["status"] == "OK"
    assert result["portfolio_state"] == "ACTIVE_PORTFOLIO"
    assert result["asset_class_exposure"] == {"CRYPTO": 40.0, "EQUITIES": 60.0}
    assert result["symbol_exposure"] == {"BTC-USD": 40.0, "SPY": 60.0}
    assert result["concentration_metrics"]["largest_symbol_concentration"] == 0.6
    assert result["diversification_metrics"]["symbol_count"] == 2


def test_runtime_exposure_builder_fails_closed_for_malformed_positions() -> None:
    result = RuntimeExposureBuilder().build([{"asset_class": "EQUITIES", "market_value": 100.0}])

    assert result["status"] == "DATA UNAVAILABLE"
    assert result["portfolio_state"] == "BROKEN_PIPELINE"
    assert "position_symbol_missing" in result["reasons"]
