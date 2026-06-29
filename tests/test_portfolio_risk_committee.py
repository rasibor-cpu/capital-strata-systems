from __future__ import annotations

from backend.portfolio.portfolio_risk_committee import PortfolioRiskCommittee


def _committee_inputs() -> dict:
    return {
        "portfolio_intelligence": {"status": "OK", "portfolio_status": "HEALTHY"},
        "capital_rotation": {"status": "OK", "target_allocations": {"CASH": 5.0, "EQUITIES": 95.0}},
        "adaptive_portfolio": {
            "status": "OK",
            "adaptive_recommendation": "INCREASE_RISK",
            "risk_committee_status": "GREEN",
            "confidence": 90,
        },
        "attribution": {"status": "OK", "recommendation": "EXPAND_WINNERS"},
        "regime_allocation": {"status": "OK", "allocation_bias": "GROWTH"},
    }


def test_portfolio_risk_committee_green_approves_advisory() -> None:
    inputs = _committee_inputs()
    result = PortfolioRiskCommittee().review(**inputs, supervisor_flags={"status": "RUNNING"})

    assert result["committee_decision"] == "APPROVE_ADVISORY"
    assert result["committee_status"] == "GREEN"
    assert result["confidence"] == 90
    assert result["advisory_only"] is True


def test_portfolio_risk_committee_rejects_conflicted_risk_increase() -> None:
    inputs = _committee_inputs()
    inputs["attribution"] = {"status": "OK", "recommendation": "REVIEW_DETRACTORS"}
    inputs["regime_allocation"] = {"status": "OK", "allocation_bias": "DEFENSIVE"}

    result = PortfolioRiskCommittee().review(**inputs, supervisor_flags={"status": "RUNNING"})

    assert result["committee_decision"] == "REJECT_RISK_INCREASE"
    assert result["committee_status"] == "AMBER"
    assert "weak_attribution" in result["concerns"]


def test_portfolio_risk_committee_red_signal_pauses_new_trades() -> None:
    inputs = _committee_inputs()
    result = PortfolioRiskCommittee().review(**inputs, supervisor_flags={"status": "RED"})

    assert result["committee_decision"] == "PAUSE_NEW_TRADES"
    assert result["committee_status"] == "RED"
    assert result["confidence"] <= 30


def test_portfolio_risk_committee_missing_input_fails_closed() -> None:
    result = PortfolioRiskCommittee().review(None, None, None, None, None)

    assert result["status"] == "DATA UNAVAILABLE"
    assert result["committee_decision"] == "PAUSE_NEW_TRADES"
    assert result["committee_status"] == "RED"
