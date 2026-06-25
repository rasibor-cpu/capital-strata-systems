from __future__ import annotations

import pytest

from backend.analytics.portfolio_correlation_engine import PortfolioCorrelationEngine, PortfolioCorrelationEngineError


def test_correlation_grouping() -> None:
    engine = PortfolioCorrelationEngine()
    summary = engine.analyze_portfolio(
        [
            {"symbol": "BTC-USD", "asset_class": "CRYPTO", "exposure_value": 5000.0},
            {"symbol": "ETH-USD", "asset_class": "CRYPTO", "exposure_value": 3000.0},
            {"symbol": "EUR_USD", "asset_class": "FX", "exposure_value": 2000.0},
        ]
    )

    assert summary["total_exposure"] == 10000.0
    assert summary["by_asset_class"]["CRYPTO"] == 8000.0
    assert summary["by_symbol"]["BTCUSD"] == 5000.0
    assert summary["grouped_exposure"]["BTC_ETH_SOL"] == 8000.0
    assert summary["correlation_score"] == 0.8


def test_fx_exposure_and_long_short_split() -> None:
    engine = PortfolioCorrelationEngine()
    summary = engine.analyze_portfolio(
        [
            {"symbol": "EUR_USD", "asset_class": "FX", "exposure_value": 7000.0, "side": "LONG"},
            {"symbol": "USD_JPY", "asset_class": "FX", "exposure_value": -3000.0, "side": "SHORT"},
        ]
    )

    assert summary["by_asset_class"]["FX"] == 10000.0
    assert summary["long_exposure"] == 7000.0
    assert summary["short_exposure"] == 3000.0
    assert summary["directional_exposure"] == 4000.0


def test_mixed_long_short_portfolio_is_deterministic() -> None:
    engine = PortfolioCorrelationEngine()
    rows = [
        {"symbol": "SPY", "asset_class": "ETF", "market_value": 2500.0, "side": "LONG"},
        {"symbol": "QQQ", "asset_class": "ETF", "market_value": 1500.0, "side": "SHORT"},
        {"symbol": "IWM", "asset_class": "ETF", "market_value": 1000.0, "side": "LONG"},
    ]

    first = engine.analyze_portfolio(rows)
    second = engine.analyze_portfolio(rows)

    assert first == second
    assert first["long_exposure"] == 3500.0
    assert first["short_exposure"] == 1500.0


def test_invalid_input_fail_closed() -> None:
    engine = PortfolioCorrelationEngine()

    with pytest.raises(PortfolioCorrelationEngineError):
        engine.analyze_portfolio(None)

    with pytest.raises(PortfolioCorrelationEngineError):
        engine.analyze_portfolio([{"asset_class": "FX", "exposure_value": 1.0}])


def test_configurable_groups_are_supported() -> None:
    engine = PortfolioCorrelationEngine(correlation_groups={"MEGA_CAP": ["AAPL", "MSFT"]})
    summary = engine.analyze_portfolio(
        [
            {"symbol": "AAPL", "asset_class": "EQUITY", "exposure_value": 1000.0},
            {"symbol": "MSFT", "asset_class": "EQUITY", "exposure_value": 2000.0},
        ]
    )

    assert summary["grouped_exposure"]["MEGA_CAP"] == 3000.0
