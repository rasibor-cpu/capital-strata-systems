from __future__ import annotations

from typing import Any, Mapping, Sequence

from backend.options.options_income_enterprise_adapter import (
    ENTERPRISE_SAFE_FLAGS,
    PAYLOAD_VERSION,
    SUBSYSTEM_ID,
    assert_enterprise_safe,
    normalize_timestamp,
    numeric,
    stable_id,
)


class OptionsIncomeLearningAdapter:
    def observations(
        self,
        outcomes: Sequence[Mapping[str, Any]],
        *,
        timestamp: str,
        certification_result: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        when = normalize_timestamp(timestamp)
        rows = []
        for outcome in outcomes:
            item = dict(outcome)
            assert_enterprise_safe({**item, **ENTERPRISE_SAFE_FLAGS})
            strategy = str(item.get("strategy", item.get("strategy_type", "UNKNOWN"))).upper()
            rows.append(
                {
                    "observation_id": stable_id("oi-learning", strategy, item.get("position_id"), when, item),
                    "payload_version": PAYLOAD_VERSION,
                    "subsystem": SUBSYSTEM_ID,
                    "timestamp": when,
                    "strategy": strategy,
                    "candidate_ranking_outcome": item.get("candidate_ranking_outcome", item.get("ranking_score")),
                    "premium_captured": numeric(item.get("premium_captured", item.get("premium_realized", 0.0)), "premium_captured", default=0.0),
                    "position_duration_days": numeric(item.get("position_duration_days", item.get("holding_period_days", 0.0)), "position_duration_days", default=0.0),
                    "assignment_outcome": str(item.get("assignment_outcome", item.get("assignment_status", "UNKNOWN"))),
                    "roll_outcome": str(item.get("roll_outcome", "UNKNOWN")),
                    "capital_efficiency": numeric(item.get("capital_efficiency", 0.0), "capital_efficiency", default=0.0),
                    "income_target_achievement": numeric(item.get("income_target_achievement", 0.0), "income_target_achievement", default=0.0),
                    "risk_limit_outcome": str(item.get("risk_limit_outcome", "UNKNOWN")),
                    "stress_test_result": str(item.get("stress_test_result", "UNKNOWN")),
                    "portfolio_performance": item.get("portfolio_performance", {}),
                    "certification_result": dict(certification_result or {}),
                    "mutates_strategy_weights": False,
                    "mutates_execution_thresholds": False,
                    "mutates_risk_limits": False,
                    "mutates_broker_settings": False,
                    **ENTERPRISE_SAFE_FLAGS,
                }
            )
        rows.sort(key=lambda row: (row["strategy"], row["observation_id"]))
        return rows


def build_options_income_learning_observations(outcomes: Sequence[Mapping[str, Any]], **kwargs: Any) -> list[dict[str, Any]]:
    return OptionsIncomeLearningAdapter().observations(outcomes, **kwargs)


__all__ = ["OptionsIncomeLearningAdapter", "build_options_income_learning_observations"]
