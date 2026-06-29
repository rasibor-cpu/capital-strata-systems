from __future__ import annotations

from backend.portfolio.constants import (
    CANONICAL_REGIMES,
    REGIME_CORRELATION_STRESS,
    REGIME_HIGH_VOLATILITY,
    REGIME_LOW_VOLATILITY,
    REGIME_RANGING,
    REGIME_TRENDING_DOWN,
    REGIME_TRENDING_UP,
    REGIME_UNKNOWN,
    RECOMMENDATION_ORDER,
)
from backend.portfolio.utils import clamp, normalize_allocations, safe_float, safe_series


def test_canonical_regime_constants_cover_phase131_outputs() -> None:
    assert {
        REGIME_TRENDING_UP,
        REGIME_TRENDING_DOWN,
        REGIME_RANGING,
        REGIME_HIGH_VOLATILITY,
        REGIME_LOW_VOLATILITY,
        REGIME_CORRELATION_STRESS,
        REGIME_UNKNOWN,
    } == CANONICAL_REGIMES


def test_recommendation_order_is_conservative_to_aggressive() -> None:
    assert RECOMMENDATION_ORDER["PAUSE_NEW_TRADES"] < RECOMMENDATION_ORDER["REDUCE_RISK"]
    assert RECOMMENDATION_ORDER["MAINTAIN"] < RECOMMENDATION_ORDER["INCREASE_RISK"]


def test_safe_float_clamp_and_series_helpers() -> None:
    assert safe_float("1.25") == 1.25
    assert safe_float("bad", default=2.0) == 2.0
    assert clamp(12, 0, 10) == 10
    assert safe_series([1, "2", "bad", None, 3.5]) == [1.0, 2.0, 3.5]


def test_normalize_allocations_non_negative_and_exact_100() -> None:
    allocations = normalize_allocations({"CRYPTO": 25, "EQUITIES": 25, "CASH": 50, "BAD": -10})

    assert all(value >= 0.0 for value in allocations.values())
    assert round(sum(allocations.values()), 2) == 100.0
