from __future__ import annotations

from backend.portfolio.policy_profile_engine import PolicyProfileEngine


def test_policy_profile_returns_known_profile() -> None:
    result = PolicyProfileEngine().get_profile("growth")

    assert result["status"] == "OK"
    assert result["active_profile"] == "GROWTH"
    assert result["profile"]["allowed_recommendation_ceiling"] == "INCREASE_RISK"
    assert result["advisory_only"] is True


def test_policy_profile_unknown_defaults_to_capital_preservation() -> None:
    result = PolicyProfileEngine().get_profile("unknown")

    assert result["active_profile"] == "CAPITAL_PRESERVATION"
    assert result["defaulted"] is True
    assert result["profile"]["allocation_bias"] == "DEFENSIVE"


def test_policy_profile_list_profiles_is_advisory() -> None:
    result = PolicyProfileEngine().list_profiles()

    assert "BALANCED" in result["profiles"]
    assert result["default_profile"] == "CAPITAL_PRESERVATION"
    assert result["advisory_only"] is True
