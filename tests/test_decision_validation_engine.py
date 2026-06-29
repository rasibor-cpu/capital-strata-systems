from __future__ import annotations

from backend.portfolio.decision_validation_engine import DecisionValidationEngine


def _policy(name: str = "GROWTH") -> dict:
    return {
        "active_profile": name,
        "profile": {
            "allowed_recommendation_ceiling": "INCREASE_RISK" if name == "GROWTH" else "MAINTAIN",
            "max_drawdown_tolerance": 0.10,
            "concentration_limit": 0.50,
            "minimum_cash_reserve": 5.0,
        },
    }


def _decision(recommendation: str = "INCREASE_RISK") -> dict:
    return {
        "portfolio_recommendation": recommendation,
        "missing_inputs": [],
        "portfolio_health": {
            "metrics": {
                "max_drawdown": 0.03,
                "largest_symbol_concentration": 0.25,
                "largest_asset_class_concentration": 0.40,
            }
        },
        "capital_rotation": {"target_allocations": {"CASH": 10.0, "EQUITIES": 90.0}},
        "risk_committee": {"committee_status": "GREEN"},
    }


def test_decision_validation_passes_green_path() -> None:
    result = DecisionValidationEngine().validate(_decision(), _policy(), {"status": "RUNNING"})

    assert result["validation_status"] == "PASS"
    assert result["violations"] == []
    assert result["advisory_only"] is True


def test_decision_validation_warns_on_cash_reserve() -> None:
    decision = _decision("MAINTAIN")
    decision["capital_rotation"] = {"target_allocations": {"CASH": 1.0, "EQUITIES": 99.0}}

    result = DecisionValidationEngine().validate(decision, _policy(), {"status": "RUNNING"})

    assert result["validation_status"] == "WARN"
    assert "cash_reserve_below_policy" in result["warnings"]


def test_decision_validation_fails_on_policy_and_committee_violations() -> None:
    decision = _decision("INCREASE_RISK")
    decision["risk_committee"] = {"committee_status": "RED"}
    result = DecisionValidationEngine().validate(decision, _policy("CONSERVATIVE"), {"status": "RUNNING"})

    assert result["validation_status"] == "FAIL"
    assert result["recommendation"] == "PAUSE_NEW_TRADES"
    assert "recommendation_exceeds_policy_ceiling" in result["violations"]
    assert "red_committee_requires_pause" in result["violations"]


def test_decision_validation_missing_data_fails_closed() -> None:
    result = DecisionValidationEngine().validate(None, None)

    assert result["status"] == "DATA UNAVAILABLE"
    assert result["validation_status"] == "FAIL"
