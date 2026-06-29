from __future__ import annotations

from typing import Any, Mapping

from backend.portfolio.constants import RECOMMENDATION_ORDER
from backend.portfolio.utils import safe_float


class DecisionValidationEngineError(RuntimeError):
    """Fail-closed exception for portfolio decision validation."""


class DecisionValidationEngine:
    """Validate advisory recommendations against policy and governance signals."""

    ORDER = RECOMMENDATION_ORDER

    def validate(
        self,
        decision_package: Mapping[str, Any] | None,
        policy_profile: Mapping[str, Any] | None,
        supervisor_state: Mapping[str, Any] | None = None,
        risk_committee: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(decision_package, Mapping):
            return self._fail("decision_package_unavailable")
        if not isinstance(policy_profile, Mapping):
            return self._fail("policy_profile_unavailable")

        violations: list[str] = []
        warnings: list[str] = []
        recommendation = str(decision_package.get("portfolio_recommendation", "")).upper()
        policy = policy_profile.get("profile", {})
        policy = policy if isinstance(policy, Mapping) else {}

        ceiling = str(policy.get("allowed_recommendation_ceiling", "PAUSE_NEW_TRADES")).upper()
        if self.ORDER.get(recommendation, 2) > self.ORDER.get(ceiling, 0):
            violations.append("recommendation_exceeds_policy_ceiling")

        health = decision_package.get("portfolio_health", {})
        health = health if isinstance(health, Mapping) else {}
        metrics = health.get("metrics", {})
        metrics = metrics if isinstance(metrics, Mapping) else {}
        drawdown = safe_float(metrics.get("max_drawdown"))
        concentration = max(
            safe_float(metrics.get("largest_symbol_concentration")),
            safe_float(metrics.get("largest_asset_class_concentration")),
        )
        if drawdown > safe_float(policy.get("max_drawdown_tolerance")):
            violations.append("drawdown_exceeds_policy")
        if concentration > safe_float(policy.get("concentration_limit")):
            violations.append("concentration_exceeds_policy")

        rotation = decision_package.get("capital_rotation", {})
        rotation = rotation if isinstance(rotation, Mapping) else {}
        allocations = rotation.get("target_allocations", {})
        if isinstance(allocations, Mapping):
            cash = safe_float(allocations.get("CASH"))
            if cash < safe_float(policy.get("minimum_cash_reserve")):
                warnings.append("cash_reserve_below_policy")

        committee = risk_committee if isinstance(risk_committee, Mapping) else decision_package.get("risk_committee", {})
        committee = committee if isinstance(committee, Mapping) else {}
        if str(committee.get("committee_status", "")).upper() == "RED" and recommendation != "PAUSE_NEW_TRADES":
            violations.append("red_committee_requires_pause")

        supervisor = supervisor_state if isinstance(supervisor_state, Mapping) else {}
        supervisor_status = str(supervisor.get("status", "")).upper()
        if supervisor_status in {"OFFLINE", "ERROR", "FAILED", "HALTED", "PAUSED", "RED"}:
            violations.append("supervisor_not_green")
        elif not supervisor_status:
            warnings.append("supervisor_status_missing")

        missing_inputs = decision_package.get("missing_inputs", [])
        if isinstance(missing_inputs, list) and missing_inputs:
            violations.append("decision_package_has_missing_inputs")

        if violations:
            status = "FAIL"
            final_recommendation = "PAUSE_NEW_TRADES"
        elif warnings:
            status = "WARN"
            final_recommendation = recommendation or "MAINTAIN"
        else:
            status = "PASS"
            final_recommendation = recommendation or "MAINTAIN"

        return {
            "status": "OK",
            "validation_status": status,
            "violations": sorted(set(violations)),
            "warnings": sorted(set(warnings)),
            "recommendation": final_recommendation,
            "advisory_only": True,
        }

    @staticmethod
    def _fail(reason: str) -> dict[str, Any]:
        return {
            "status": "DATA UNAVAILABLE",
            "validation_status": "FAIL",
            "violations": [reason],
            "warnings": [],
            "recommendation": "PAUSE_NEW_TRADES",
            "advisory_only": True,
        }
