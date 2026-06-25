from __future__ import annotations

from typing import Any, Mapping


class AutonomousLearningControllerError(RuntimeError):
    """Fail-closed exception for autonomous learning packaging."""


class AutonomousLearningController:
    """Merge operational intelligence outputs into a deterministic learning package."""

    def build_learning_package(
        self,
        *,
        trade_forensics: list[Mapping[str, Any]] | None,
        performance_attribution: Mapping[str, Any] | None,
        opportunity_cost: Mapping[str, Any] | None,
        strategy_league_table: list[Mapping[str, Any]] | None,
        improvement_recommendations: list[Mapping[str, Any]] | None,
    ) -> dict[str, Any]:
        if performance_attribution is not None and not isinstance(performance_attribution, Mapping):
            raise AutonomousLearningControllerError("performance_attribution must be a mapping when provided")
        if opportunity_cost is not None and not isinstance(opportunity_cost, Mapping):
            raise AutonomousLearningControllerError("opportunity_cost must be a mapping when provided")

        forensics_rows = sorted(list(trade_forensics or []), key=lambda item: str(item.get("trade_id", "")))
        league_rows = sorted(list(strategy_league_table or []), key=lambda item: str(item.get("strategy_id", "")))
        recommendation_rows = sorted(list(improvement_recommendations or []), key=lambda item: str(item.get("action", "")))
        attribution = dict(performance_attribution or {})
        cost = dict(opportunity_cost or {})

        trade_count = len(forensics_rows)
        optimal_decisions = sum(1 for row in forensics_rows if bool(row.get("decision_optimal", False)))
        optimality_rate = (optimal_decisions / trade_count) if trade_count else 0.0

        top_strategy = league_rows[0]["strategy_id"] if league_rows else ""
        missed_total = self._float(cost.get("summary", {}).get("missed_opportunity_total", 0.0))

        return {
            "trade_forensics": forensics_rows,
            "performance_attribution": attribution,
            "opportunity_cost": cost,
            "strategy_league_table": league_rows,
            "improvement_recommendations": recommendation_rows,
            "learning_summary": {
                "trade_count": trade_count,
                "optimality_rate": round(optimality_rate, 8),
                "top_strategy": top_strategy,
                "missed_opportunity_total": round(missed_total, 8),
                "recommendation_count": len(recommendation_rows),
            },
            "learning_priority": self._priority(missed_total, optimality_rate),
        }

    @staticmethod
    def _priority(missed_total: float, optimality_rate: float) -> str:
        if missed_total > 0.0 and optimality_rate < 0.5:
            return "HIGH"
        if missed_total > 0.0 or optimality_rate < 0.7:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
