from __future__ import annotations

from backend.portfolio.capital_rotation_engine import CapitalRotationEngine


def test_capital_rotation_allocations_are_non_negative_and_sum_to_100() -> None:
    candidates = [
        {
            "asset_class": "CRYPTO",
            "current_allocation": 45.0,
            "expected_return": 0.15,
            "drawdown": 0.20,
            "sortino": 0.4,
            "capital_efficiency": 0.25,
            "concentration": 0.7,
            "correlation": 0.85,
        },
        {
            "asset_class": "EQUITIES",
            "current_allocation": 35.0,
            "expected_return": 0.08,
            "drawdown": 0.04,
            "sortino": 1.8,
            "capital_efficiency": 0.80,
            "concentration": 0.3,
            "correlation": 0.25,
        },
        {
            "asset_class": "FX",
            "current_allocation": 20.0,
            "expected_return": 0.04,
            "drawdown": 0.03,
            "sortino": 1.4,
            "capital_efficiency": 0.70,
            "concentration": 0.2,
            "correlation": 0.20,
        },
    ]

    result = CapitalRotationEngine().recommend(candidates, {"portfolio_status": "WATCH"})

    assert result["status"] == "OK"
    assert result["advisory_only"] is True
    assert result["execution_allowed"] is False
    assert min(result["target_allocations"].values()) >= 0.0
    assert sum(result["target_allocations"].values()) == 100.0
    assert result["target_allocations"]["CRYPTO"] < 45.0
    assert result["target_allocations"]["EQUITIES"] > result["target_allocations"]["FX"]


def test_capital_rotation_is_deterministic_for_input_order() -> None:
    candidates = [
        {"asset_class": "FX", "current_allocation": 33.33, "sortino": 1.1, "capital_efficiency": 0.6},
        {"asset_class": "CRYPTO", "current_allocation": 33.33, "drawdown": 0.1, "correlation": 0.7},
        {"asset_class": "EQUITIES", "current_allocation": 33.34, "sortino": 1.7, "capital_efficiency": 0.8},
    ]

    first = CapitalRotationEngine().recommend(candidates)
    second = CapitalRotationEngine().recommend(list(reversed(candidates)))

    assert first == second
    assert sum(first["target_allocations"].values()) == 100.0


def test_capital_rotation_fails_closed_to_cash_when_data_unavailable() -> None:
    result = CapitalRotationEngine().recommend(None)

    assert result["status"] == "DATA UNAVAILABLE"
    assert result["target_allocations"] == {"CASH": 100.0}
    assert result["total_allocation"] == 100.0
    assert result["recommendation"] == "NO_ACTION"
