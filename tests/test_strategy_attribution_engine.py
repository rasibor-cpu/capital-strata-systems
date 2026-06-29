from __future__ import annotations

from backend.portfolio.strategy_attribution_engine import StrategyAttributionEngine


def test_strategy_attribution_summarizes_groups_and_winners() -> None:
    trades = [
        {
            "strategy_id": "trend",
            "asset_class": "equities",
            "symbol": "SPY",
            "market_regime": "trending",
            "timestamp_close": "2026-06-28T10:00:00Z",
            "realized_pnl": 120.0,
        },
        {
            "strategy_id": "trend",
            "asset_class": "equities",
            "symbol": "QQQ",
            "market_regime": "trending",
            "timestamp_close": "2026-06-28T11:00:00Z",
            "realized_pnl": 80.0,
        },
        {
            "strategy_id": "carry",
            "asset_class": "fx",
            "symbol": "EUR_USD",
            "market_regime": "low_volatility",
            "timestamp_close": "2026-06-29T11:00:00Z",
            "realized_pnl": 40.0,
        },
    ]

    result = StrategyAttributionEngine().analyze(trades)

    assert result["status"] == "OK"
    assert result["recommendation"] == "EXPAND_WINNERS"
    assert result["strategy_attribution"]["TREND"]["trade_count"] == 2
    assert result["asset_class_attribution"]["EQUITIES"]["total_pnl"] == 200.0
    assert result["time_bucket_attribution"]["2026-06-28"]["trade_count"] == 2
    assert result["top_contributors"][0]["symbol"] == "SPY"


def test_strategy_attribution_reviews_detractors() -> None:
    result = StrategyAttributionEngine().analyze(
        [
            {"strategy_id": "mean", "asset_class": "crypto", "symbol": "BTC-USD", "realized_pnl": -50.0},
            {"strategy_id": "mean", "asset_class": "crypto", "symbol": "ETH-USD", "realized_pnl": 10.0},
        ]
    )

    assert result["recommendation"] == "REVIEW_DETRACTORS"
    assert result["top_detractors"][0]["symbol"] == "BTC-USD"


def test_strategy_attribution_empty_history_is_safe() -> None:
    result = StrategyAttributionEngine().analyze([])

    assert result["status"] == "DATA UNAVAILABLE"
    assert result["recommendation"] == "MAINTAIN"
    assert result["strategy_attribution"] == {}
