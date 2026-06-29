from __future__ import annotations

from typing import Any


class PolicyProfileEngineError(RuntimeError):
    """Fail-closed exception for policy profile lookup."""


class PolicyProfileEngine:
    """Institutional advisory risk policy profiles."""

    DEFAULT_PROFILE = "CAPITAL_PRESERVATION"

    PROFILES = {
        "CONSERVATIVE": {
            "max_drawdown_tolerance": 0.08,
            "concentration_limit": 0.35,
            "minimum_cash_reserve": 20.0,
            "max_risk_budget_utilization": 0.55,
            "allocation_bias": "DEFENSIVE",
            "allowed_recommendation_ceiling": "MAINTAIN",
        },
        "BALANCED": {
            "max_drawdown_tolerance": 0.12,
            "concentration_limit": 0.45,
            "minimum_cash_reserve": 12.5,
            "max_risk_budget_utilization": 0.70,
            "allocation_bias": "BALANCED",
            "allowed_recommendation_ceiling": "REDUCE_RISK",
        },
        "GROWTH": {
            "max_drawdown_tolerance": 0.18,
            "concentration_limit": 0.55,
            "minimum_cash_reserve": 7.5,
            "max_risk_budget_utilization": 0.85,
            "allocation_bias": "GROWTH",
            "allowed_recommendation_ceiling": "INCREASE_RISK",
        },
        "CAPITAL_PRESERVATION": {
            "max_drawdown_tolerance": 0.05,
            "concentration_limit": 0.30,
            "minimum_cash_reserve": 30.0,
            "max_risk_budget_utilization": 0.40,
            "allocation_bias": "DEFENSIVE",
            "allowed_recommendation_ceiling": "PAUSE_NEW_TRADES",
        },
        "HIGH_CONVICTION": {
            "max_drawdown_tolerance": 0.15,
            "concentration_limit": 0.65,
            "minimum_cash_reserve": 10.0,
            "max_risk_budget_utilization": 0.90,
            "allocation_bias": "FOCUSED",
            "allowed_recommendation_ceiling": "INCREASE_RISK",
        },
    }

    def get_profile(self, profile_name: Any = None) -> dict[str, Any]:
        requested = str(profile_name or self.DEFAULT_PROFILE).strip().upper()
        active = requested if requested in self.PROFILES else self.DEFAULT_PROFILE
        profile = dict(self.PROFILES[active])
        return {
            "status": "OK",
            "requested_profile": requested,
            "active_profile": active,
            "profile": profile,
            "defaulted": active != requested,
            "advisory_only": True,
        }

    def list_profiles(self) -> dict[str, Any]:
        return {
            "status": "OK",
            "profiles": {name: dict(values) for name, values in sorted(self.PROFILES.items())},
            "default_profile": self.DEFAULT_PROFILE,
            "advisory_only": True,
        }
