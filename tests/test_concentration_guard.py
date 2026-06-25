from __future__ import annotations

import pytest

from backend.analytics.concentration_guard import ConcentrationGuard, ConcentrationGuardError


def test_recommendation_generation_allow_reduce_block() -> None:
    guard = ConcentrationGuard(
        concentration_reduce_threshold=0.40,
        concentration_block_threshold=0.60,
        correlation_reduce_threshold=0.35,
        correlation_block_threshold=0.55,
    )

    allow = guard.evaluate(
        [
            {"symbol": "AAPL", "asset_class": "EQUITY", "exposure_value": 500.0, "side": "LONG"},
            {"symbol": "TLT", "asset_class": "BOND", "exposure_value": 500.0, "side": "SHORT"},
            {"symbol": "GLD", "asset_class": "COMMODITY", "exposure_value": 500.0, "side": "LONG"},
        ]
    )
    reduce = guard.evaluate(
        [
            {"symbol": "BTC-USD", "asset_class": "CRYPTO", "exposure_value": 5000.0},
            {"symbol": "ETH-USD", "asset_class": "CRYPTO", "exposure_value": 1000.0},
            {"symbol": "SOL-USD", "asset_class": "CRYPTO", "exposure_value": 500.0},
        ]
    )
    block = guard.evaluate(
        [
            {"symbol": "BTC-USD", "asset_class": "CRYPTO", "exposure_value": 9000.0},
            {"symbol": "ETH-USD", "asset_class": "CRYPTO", "exposure_value": 1000.0},
        ]
    )

    assert allow["recommendation"] == "ALLOW"
    assert reduce["recommendation"] in {"REDUCE_SIZE", "BLOCK"}
    assert block["recommendation"] == "BLOCK"


def test_correlated_crypto_exposure() -> None:
    guard = ConcentrationGuard()
    result = guard.evaluate(
        [
            {"symbol": "BTC-USD", "asset_class": "CRYPTO", "exposure_value": 5000.0},
            {"symbol": "ETH-USD", "asset_class": "CRYPTO", "exposure_value": 3000.0},
            {"symbol": "SOL-USD", "asset_class": "CRYPTO", "exposure_value": 2000.0},
        ]
    )

    assert result["correlation_score"] == 1.0
    assert result["recommendation"] in {"REDUCE_SIZE", "BLOCK"}


def test_long_only_concentration_and_threshold_enforcement() -> None:
    guard = ConcentrationGuard(concentration_reduce_threshold=0.30, concentration_block_threshold=0.50)
    result = guard.evaluate(
        [
            {"symbol": "SPY", "asset_class": "EQUITY", "market_value": 9000.0, "side": "LONG"},
            {"symbol": "QQQ", "asset_class": "EQUITY", "market_value": 1000.0, "side": "LONG"},
        ]
    )

    assert result["concentration_score"] >= 0.5
    assert result["recommendation"] == "BLOCK"


def test_mixed_long_short_portfolio() -> None:
    guard = ConcentrationGuard()
    result = guard.evaluate(
        [
            {"symbol": "AAPL", "asset_class": "EQUITY", "market_value": 4000.0, "side": "LONG"},
            {"symbol": "MSFT", "asset_class": "EQUITY", "market_value": 2500.0, "side": "SHORT"},
        ]
    )

    assert result["risk_score"] >= 0.0
    assert result["recommendation"] in {"ALLOW", "REDUCE_SIZE", "BLOCK"}


def test_fail_closed_validation() -> None:
    guard = ConcentrationGuard()

    with pytest.raises(ConcentrationGuardError):
        guard.evaluate([{"asset_class": "FX", "exposure_value": 1.0}])

    with pytest.raises(ConcentrationGuardError):
        ConcentrationGuard(concentration_reduce_threshold=-0.1)


def test_deterministic_output() -> None:
    guard = ConcentrationGuard()
    positions = [
        {"symbol": "EUR_USD", "asset_class": "FX", "exposure_value": 3000.0},
        {"symbol": "GBP_USD", "asset_class": "FX", "exposure_value": 3000.0},
    ]

    assert guard.evaluate(positions) == guard.evaluate(positions)
