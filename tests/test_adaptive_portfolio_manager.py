from __future__ import annotations

from backend.portfolio.adaptive_portfolio_manager import AdaptivePortfolioManager


def _healthy_intelligence() -> dict:
    return {
        "status": "OK",
        "portfolio_status": "HEALTHY",
        "intelligence_score": 92.0,
        "metrics": {
            "max_drawdown": 0.03,
            "largest_symbol_concentration": 0.30,
            "largest_asset_class_concentration": 0.40,
        },
    }


def test_adaptive_portfolio_green_case_supports_selective_risk_increase() -> None:
    result = AdaptivePortfolioManager().evaluate(
        portfolio_intelligence=_healthy_intelligence(),
        capital_rotation={
            "status": "OK",
            "recommendation": "ROTATE_CAPITAL",
            "target_allocations": {"CASH": 5.0, "EQUITIES": 55.0, "FX": 40.0},
        },
        supervisor_state={"status": "RUNNING"},
        risk_context={"status": "GREEN", "critical_flags": []},
        governance_context={"status": "GREEN", "critical_flags": []},
    )

    assert result["status"] == "OK"
    assert result["adaptive_recommendation"] == "INCREASE_RISK"
    assert result["risk_committee_status"] == "GREEN"
    assert result["capital_rotation_action"] == "OPPORTUNISTIC"
    assert result["advisory_only"] is True


def test_adaptive_portfolio_conflicting_signal_reduces_confidence() -> None:
    result = AdaptivePortfolioManager().evaluate(
        portfolio_intelligence=_healthy_intelligence(),
        capital_rotation={
            "status": "OK",
            "recommendation": "ROTATE_CAPITAL",
            "target_allocations": {"CASH": 45.0, "EQUITIES": 35.0, "FX": 20.0},
        },
        supervisor_state={"status": "RUNNING"},
        risk_context={"status": "GREEN", "critical_flags": []},
        governance_context={"status": "GREEN", "critical_flags": []},
    )

    assert result["adaptive_recommendation"] == "MAINTAIN"
    assert result["risk_committee_status"] == "AMBER"
    assert result["confidence"] < 92
    assert "capital_rotation_defensive" in result["risk_flags"]


def test_adaptive_portfolio_red_safety_signal_pauses_new_trades() -> None:
    result = AdaptivePortfolioManager().evaluate(
        portfolio_intelligence=_healthy_intelligence(),
        capital_rotation={
            "status": "OK",
            "recommendation": "ROTATE_CAPITAL",
            "target_allocations": {"CASH": 5.0, "EQUITIES": 55.0, "FX": 40.0},
        },
        supervisor_state={"status": "RUNNING"},
        risk_context={"status": "RED", "critical_flags": ["CRITICAL"]},
        governance_context={"status": "GREEN", "critical_flags": []},
    )

    assert result["adaptive_recommendation"] == "PAUSE_NEW_TRADES"
    assert result["risk_committee_status"] == "RED"
    assert result["advisory_only"] is True


def test_adaptive_portfolio_missing_inputs_fail_closed() -> None:
    result = AdaptivePortfolioManager().evaluate(None, None, None)

    assert result["status"] == "DATA UNAVAILABLE"
    assert result["adaptive_recommendation"] == "PAUSE_NEW_TRADES"
    assert result["risk_committee_status"] == "RED"
    assert result["confidence"] <= 30
    assert result["advisory_only"] is True
