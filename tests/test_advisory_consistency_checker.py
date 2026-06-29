from __future__ import annotations

from backend.portfolio.advisory_consistency_checker import AdvisoryConsistencyChecker


def test_advisory_consistency_checker_green_consistent_case() -> None:
    result = AdvisoryConsistencyChecker().check(
        adaptive_portfolio={"adaptive_recommendation": "MAINTAIN"},
        capital_rotation={"recommendation": "ROTATE_CAPITAL"},
        risk_committee={"committee_decision": "APPROVE_ADVISORY", "committee_status": "GREEN"},
        policy_profile={"profile": {"allowed_recommendation_ceiling": "INCREASE_RISK"}},
        market_regime={"risk_bias": "BALANCED"},
    )

    assert result["consistent"] is True
    assert result["conflicts"] == []
    assert result["advisory_only"] is True


def test_advisory_consistency_checker_detects_conflicts() -> None:
    result = AdvisoryConsistencyChecker().check(
        adaptive_portfolio={"adaptive_recommendation": "INCREASE_RISK"},
        capital_rotation={"recommendation": "ROTATE_CAPITAL"},
        risk_committee={"committee_decision": "PAUSE_NEW_TRADES", "committee_status": "RED"},
        policy_profile={"profile": {"allowed_recommendation_ceiling": "MAINTAIN"}},
        market_regime={"risk_bias": "DEFENSIVE"},
    )

    assert result["consistent"] is False
    assert "adaptive_increase_conflicts_with_red_committee" in result["conflicts"]
    assert "adaptive_recommendation_exceeds_policy_ceiling" in result["conflicts"]
    assert result["recommended_resolution"] == "Use the most conservative advisory signal."
