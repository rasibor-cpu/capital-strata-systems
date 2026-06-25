from __future__ import annotations

from typing import Any, Mapping


class StrategyLeagueTableError(RuntimeError):
    """Fail-closed exception for strategy league ranking."""


class StrategyLeagueTable:
    def rank_strategies(self, strategy_rows: list[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
        rows = strategy_rows if isinstance(strategy_rows, list) else []
        if not rows:
            return []

        ranked = [self._normalize(row) for row in rows]
        ranked.sort(key=lambda item: (-item["league_score"], -item["sample_size"], item["strategy_id"]))
        return ranked

    def _normalize(self, row: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(row, Mapping):
            raise StrategyLeagueTableError("strategy row must be a mapping")

        strategy_id = str(row.get("strategy_id") or "").strip()
        if not strategy_id:
            raise StrategyLeagueTableError("strategy_id must be non-empty")

        win_rate = self._float(row.get("win_rate", 0.0))
        profit_factor = self._float(row.get("profit_factor", 0.0))
        expectancy = self._float(row.get("expectancy", 0.0))
        stability = self._float(row.get("stability", row.get("stability_score", 0.0)))
        drawdown = self._float(row.get("drawdown", row.get("max_drawdown", 0.0)))
        sample_size = int(row.get("sample_size", row.get("trade_count", 0)) or 0)
        recent_trend = self._float(row.get("recent_trend", 0.0))

        score = (
            win_rate * 35.0
            + min(3.0, profit_factor) * 15.0
            + self._clamp01((expectancy + 1.0) / 2.0) * 15.0
            + self._clamp01(stability) * 15.0
            + self._clamp01(1.0 - drawdown) * 10.0
            + self._clamp01(sample_size / 50.0) * 5.0
            + self._clamp01((recent_trend + 1.0) / 2.0) * 5.0
        )
        grade = self._grade(score, sample_size, win_rate, drawdown, recent_trend)

        return {
            "strategy_id": strategy_id,
            "win_rate": round(win_rate, 8),
            "profit_factor": round(profit_factor, 8),
            "expectancy": round(expectancy, 8),
            "stability": round(stability, 8),
            "drawdown": round(drawdown, 8),
            "sample_size": sample_size,
            "recent_trend": round(recent_trend, 8),
            "league_score": round(score, 8),
            "grade": grade,
        }

    @staticmethod
    def _grade(score: float, sample_size: int, win_rate: float, drawdown: float, recent_trend: float) -> str:
        if sample_size <= 0 or win_rate < 0.30:
            return "DISABLED"
        if recent_trend <= -0.50 or drawdown >= 0.35:
            return "WATCHLIST"
        if score >= 85.0 and sample_size >= 20:
            return "PLATINUM"
        if score >= 70.0:
            return "GOLD"
        if score >= 55.0:
            return "SILVER"
        if score >= 40.0:
            return "BRONZE"
        return "WATCHLIST"

    @staticmethod
    def _float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _clamp01(value: float) -> float:
        return max(0.0, min(1.0, float(value)))
