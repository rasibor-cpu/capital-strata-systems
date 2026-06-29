from __future__ import annotations

from backend.portfolio.constants import (
    REGIME_CORRELATION_STRESS,
    REGIME_HIGH_VOLATILITY,
    REGIME_TRENDING_DOWN,
    REGIME_TRENDING_UP,
    REGIME_UNKNOWN,
)
from backend.portfolio.regime_aware_allocation import RegimeAwareAllocationEngine


def _assert_allocation_integrity(result: dict) -> None:
    allocations = result["regime_adjusted_allocations"]
    assert all(value >= 0.0 for value in allocations.values())
    assert round(sum(allocations.values()), 2) == 100.0


def test_trending_up_can_support_selective_risk_on_when_downside_ok() -> None:
    result = RegimeAwareAllocationEngine().adjust(
        {"EQUITIES": 45.0, "FX": 35.0, "CASH": 20.0},
        {"detected_regime": REGIME_TRENDING_UP, "max_drawdown": 0.02, "risk_status": "GREEN"},
    )

    assert result["detected_regime"] == REGIME_TRENDING_UP
    assert result["allocation_bias"] == "GROWTH"
    assert result["regime_adjusted_allocations"]["CASH"] == 15.0
    _assert_allocation_integrity(result)


def test_trending_down_is_defensive() -> None:
    result = RegimeAwareAllocationEngine().adjust(
        {"CRYPTO": 25.0, "EQUITIES": 55.0, "CASH": 20.0},
        {"detected_regime": REGIME_TRENDING_DOWN, "max_drawdown": 0.03},
    )

    assert result["detected_regime"] == REGIME_TRENDING_DOWN
    assert result["allocation_bias"] == "DEFENSIVE"
    assert result["regime_adjusted_allocations"]["CASH"] > 20.0
    _assert_allocation_integrity(result)


def test_correlation_stress_is_defensive() -> None:
    result = RegimeAwareAllocationEngine().adjust(
        {"CRYPTO": 30.0, "EQUITIES": 50.0, "CASH": 20.0},
        {"detected_regime": REGIME_CORRELATION_STRESS, "max_drawdown": 0.03},
    )

    assert result["detected_regime"] == REGIME_CORRELATION_STRESS
    assert result["allocation_bias"] == "DEFENSIVE"
    assert result["regime_adjusted_allocations"]["CRYPTO"] < 30.0
    _assert_allocation_integrity(result)


def test_high_volatility_is_defensive() -> None:
    result = RegimeAwareAllocationEngine().adjust(
        {"CRYPTO": 30.0, "EQUITIES": 50.0, "CASH": 20.0},
        {"detected_regime": REGIME_HIGH_VOLATILITY, "max_drawdown": 0.03},
    )

    assert result["detected_regime"] == REGIME_HIGH_VOLATILITY
    assert result["allocation_bias"] == "DEFENSIVE"
    assert result["regime_adjusted_allocations"]["CASH"] > 20.0
    _assert_allocation_integrity(result)


def test_unknown_is_conservative_fail_safe() -> None:
    result = RegimeAwareAllocationEngine().adjust(
        {"EQUITIES": 70.0, "CASH": 30.0},
        {"detected_regime": "NOT_A_REGIME"},
    )

    assert result["detected_regime"] == REGIME_UNKNOWN
    assert result["allocation_bias"] == "DEFENSIVE"
    assert result["regime_adjusted_allocations"]["CASH"] > 30.0
    _assert_allocation_integrity(result)
