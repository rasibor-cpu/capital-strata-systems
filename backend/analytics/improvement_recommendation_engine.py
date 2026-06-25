from __future__ import annotations

from typing import Any, Mapping


class ImprovementRecommendationEngineError(RuntimeError):
    """Fail-closed exception for improvement recommendations."""


class ImprovementRecommendationEngine:
    def recommend(
        self,
        *,
        performance_summary: Mapping[str, Any] | None = None,
        strategy_league_table: list[Mapping[str, Any]] | None = None,
        opportunity_cost: Mapping[str, Any] | None = None,
        attribution: Mapping[str, Any] | None = None,
        health_summary: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        performance_summary = dict(performance_summary or {})
        strategy_league_table = list(strategy_league_table or [])
        opportunity_cost = dict(opportunity_cost or {})
        attribution = dict(attribution or {})
        health_summary = dict(health_summary or {})

        recommendations: list[dict[str, Any]] = []
        win_rate = self._float(performance_summary.get("win_rate", 0.0))
        profit_factor = self._float(performance_summary.get("profit_factor", 0.0))
        drawdown = self._float(performance_summary.get("max_drawdown", performance_summary.get("drawdown", 0.0)))
        exit_confidence = self._float(performance_summary.get("exit_confidence", 0.0))

        top_strategy = strategy_league_table[0] if strategy_league_table else None
        weak_strategies = [row for row in strategy_league_table if str(row.get("grade", "")).upper() in {"WATCHLIST", "DISABLED"}]

        if profit_factor >= 1.4 and win_rate >= 0.55:
            recommendations.append(self._recommend("increase allocation", "positive edge and win rate support scale-up", "high"))
        if profit_factor < 1.0 or drawdown >= 0.20 or win_rate < 0.45:
            recommendations.append(self._recommend("reduce allocation", "performance or drawdown indicates exposure should contract", "high"))
        if exit_confidence and exit_confidence < 0.60:
            recommendations.append(self._recommend("tighten exit confidence", "exit quality is not yet stable", "medium"))
        if top_strategy and str(top_strategy.get("grade", "")).upper() in {"PLATINUM", "GOLD"} and int(top_strategy.get("sample_size", 0) or 0) >= 20:
            recommendations.append(self._recommend("promote strong strategy", "top ranked strategy is proven and stable", "medium"))
        if weak_strategies:
            recommendations.append(self._recommend("pause weak strategy", "one or more strategies remain in watchlist or disabled state", "high"))

        missed = opportunity_cost.get("summary", {}).get("missed_opportunity_total", 0.0)
        if self._float(missed) > 0.0 and any(item.get("threshold_implication") == "relax_acceptance_threshold" for item in opportunity_cost.get("opportunity_costs", [])):
            recommendations.append(self._recommend("relax acceptance threshold", "rejected trades show positive expected value", "medium"))
        elif self._float(opportunity_cost.get("summary", {}).get("rejected_trade_count", 0)) > 0 and self._float(missed) <= 0.0:
            recommendations.append(self._recommend("raise acceptance threshold", "rejected flow does not show positive expected value", "medium"))

        if attribution.get("market_regime"):
            weak_regimes = [row for row in attribution.get("market_regime", []) if self._float(row.get("win_rate", 0.0)) < 0.45]
            if weak_regimes:
                recommendations.append(self._recommend("reduce exposure in weak regime", "one or more regimes remain structurally weak", "high"))

        if health_summary.get("status") == "CRITICAL":
            recommendations.append(self._recommend("reduce exposure in weak regime", "runtime health is critical", "critical"))

        return sorted(recommendations, key=lambda item: (item["priority_rank"], item["action"]))

    @staticmethod
    def _recommend(action: str, rationale: str, priority: str) -> dict[str, Any]:
        priority_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(priority, 3)
        return {
            "action": action,
            "rationale": rationale,
            "priority": priority,
            "priority_rank": priority_rank,
        }

    @staticmethod
    def _float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
