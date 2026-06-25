from __future__ import annotations

from typing import Any, Mapping


class StrategyPromotionManagerError(RuntimeError):
    """Fail-closed exception for deterministic promotion management."""


class StrategyPromotionManager:
    """Convert strategy league table grades into deterministic lifecycle recommendations."""

    def recommend(self, strategy_league_table: list[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
        rows = strategy_league_table if isinstance(strategy_league_table, list) else []
        recommendations = [self._recommend_one(row) for row in rows]
        return sorted(recommendations, key=lambda item: (item["strategy_id"], item["recommendation"]))

    def _recommend_one(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, Mapping):
            raise StrategyPromotionManagerError("strategy row must be a mapping")

        strategy_id = str(payload.get("strategy_id") or "").strip()
        if not strategy_id:
            raise StrategyPromotionManagerError("strategy_id must be non-empty")

        grade = str(payload.get("grade") or "WATCHLIST").strip().upper()
        sample_size = int(payload.get("sample_size", payload.get("trade_count", 0)) or 0)
        recent_trend = self._float(payload.get("recent_trend", 0.0))
        drawdown = self._float(payload.get("drawdown", payload.get("max_drawdown", 0.0)))

        if grade == "DISABLED" or sample_size <= 0:
            recommendation = "DISABLE"
        elif grade == "PLATINUM" and sample_size >= 20 and recent_trend >= 0.0:
            recommendation = "PROMOTE"
        elif grade == "GOLD" and sample_size >= 15 and recent_trend >= -0.1:
            recommendation = "KEEP"
        elif grade in {"SILVER", "BRONZE"} and drawdown < 0.25:
            recommendation = "WATCH"
        elif grade == "WATCHLIST" and drawdown >= 0.30:
            recommendation = "DEMOTE"
        elif grade == "WATCHLIST":
            recommendation = "WATCH"
        else:
            recommendation = "KEEP"

        return {
            "strategy_id": strategy_id,
            "grade": grade,
            "sample_size": sample_size,
            "recent_trend": round(recent_trend, 8),
            "drawdown": round(drawdown, 8),
            "recommendation": recommendation,
        }

    @staticmethod
    def _float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
