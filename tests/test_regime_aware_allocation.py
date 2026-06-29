from __future__ import annotations

from backend.portfolio.regime_aware_allocation import RegimeAwareAllocationEngine


def test_regime_aware_allocation_high_volatility_is_defensive() -> None:
    result = RegimeAwareAllocationEngine().adjust(
        {"CRYPTO": 30.0, "EQUITIES": 50.0, "CASH": 20.0},
        {"detected_regime": "HIGH_VOLATILITY", "max_drawdown": 0.05},
    )

    allocations = result["regime_adjusted_allocations"]
    assert result["detected_regime"] == "HIGH_VOLATILITY"
    assert result["allocation_bias"] == "DEFENSIVE"
    assert all(value >= 0.0 for value in allocations.values())
    assert round(sum(allocations.values()), 2) == 100.0
    assert allocations["CASH"] > 20.0
    assert allocations["CRYPTO"] < 30.0


def test_regime_aware_allocation_trending_can_shift_from_cash() -> None:
    result = RegimeAwareAllocationEngine().adjust(
        {"EQUITIES": 45.0, "FX": 35.0, "CASH": 20.0},
        {"detected_regime": "TRENDING", "max_drawdown": 0.02, "risk_status": "GREEN"},
    )

    allocations = result["regime_adjusted_allocations"]
    assert result["allocation_bias"] == "GROWTH"
    assert allocations["CASH"] == 15.0
    assert round(sum(allocations.values()), 2) == 100.0


def test_regime_aware_allocation_missing_base_fails_closed_to_cash() -> None:
    result = RegimeAwareAllocationEngine().adjust(None, None)

    assert result["status"] == "DATA UNAVAILABLE"
    assert result["detected_regime"] == "UNKNOWN"
    assert result["regime_adjusted_allocations"] == {"CASH": 100.0}
