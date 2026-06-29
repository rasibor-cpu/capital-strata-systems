from __future__ import annotations

from typing import Any, Mapping


class AdvisoryConsistencyCheckerError(RuntimeError):
    """Fail-closed exception for advisory consistency checks."""


class AdvisoryConsistencyChecker:
    """Detect conflicting advisory recommendations without execution authority."""

    ORDER = {
        "PAUSE_NEW_TRADES": 0,
        "REDUCE_RISK": 1,
        "MAINTAIN": 2,
        "REBALANCE": 2,
        "INCREASE_RISK": 3,
    }

    def check(
        self,
        adaptive_portfolio: Mapping[str, Any] | None = None,
        capital_rotation: Mapping[str, Any] | None = None,
        risk_committee: Mapping[str, Any] | None = None,
        policy_profile: Mapping[str, Any] | None = None,
        market_regime: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        conflicts: list[str] = []

        adaptive_recommendation = self._recommendation(adaptive_portfolio, "adaptive_recommendation")
        committee_decision = self._recommendation(risk_committee, "committee_decision")
        committee_status = str((risk_committee or {}).get("committee_status", "")).upper() if isinstance(risk_committee, Mapping) else ""
        rotation_recommendation = self._recommendation(capital_rotation, "recommendation")
        policy_ceiling = self._policy_ceiling(policy_profile)
        regime_bias = str((market_regime or {}).get("risk_bias", "")).upper() if isinstance(market_regime, Mapping) else ""

        if adaptive_recommendation == "INCREASE_RISK" and committee_decision in {"PAUSE_NEW_TRADES", "REJECT_RISK_INCREASE"}:
            conflicts.append("adaptive_increase_conflicts_with_risk_committee")
        if adaptive_recommendation == "INCREASE_RISK" and committee_status == "RED":
            conflicts.append("adaptive_increase_conflicts_with_red_committee")
        if adaptive_recommendation == "INCREASE_RISK" and regime_bias == "DEFENSIVE":
            conflicts.append("adaptive_increase_conflicts_with_defensive_regime")
        if rotation_recommendation == "ROTATE_CAPITAL" and committee_decision == "PAUSE_NEW_TRADES":
            conflicts.append("capital_rotation_conflicts_with_committee_pause")
        if policy_ceiling and self.ORDER.get(adaptive_recommendation, 2) > self.ORDER.get(policy_ceiling, 0):
            conflicts.append("adaptive_recommendation_exceeds_policy_ceiling")

        consistent = not conflicts
        return {
            "status": "OK",
            "consistent": consistent,
            "conflicts": sorted(set(conflicts)),
            "recommended_resolution": "Proceed with advisory package." if consistent else "Use the most conservative advisory signal.",
            "advisory_only": True,
        }

    @staticmethod
    def _recommendation(payload: Mapping[str, Any] | None, key: str) -> str:
        if not isinstance(payload, Mapping):
            return ""
        return str(payload.get(key, "")).upper()

    @staticmethod
    def _policy_ceiling(policy_profile: Mapping[str, Any] | None) -> str:
        if not isinstance(policy_profile, Mapping):
            return ""
        profile = policy_profile.get("profile", {})
        if not isinstance(profile, Mapping):
            return ""
        return str(profile.get("allowed_recommendation_ceiling", "")).upper()
