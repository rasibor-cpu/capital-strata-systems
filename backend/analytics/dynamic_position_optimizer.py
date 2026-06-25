from __future__ import annotations

from typing import Any, Mapping


class DynamicPositionOptimizerError(RuntimeError):
    """Fail-closed exception for dynamic position optimization recommendations."""


class DynamicPositionOptimizer:
    """Recommend deterministic position sizing actions without changing live sizing."""

    _GRADE_MULTIPLIER = {
        "PLATINUM": 1.15,
        "GOLD": 1.08,
        "SILVER": 1.00,
        "BRONZE": 0.92,
        "WATCHLIST": 0.75,
        "DISABLED": 0.0,
    }
    _REGIME_MULTIPLIER = {
        "TREND": 1.10,
        "TRENDING": 1.10,
        "RANGE": 0.95,
        "RANGING": 0.95,
        "VOLATILE": 0.80,
        "HIGH_VOLATILITY": 0.80,
        "BREAKOUT": 1.05,
        "REVERSAL": 0.90,
        "UNKNOWN": 0.90,
    }

    def recommend(self, rows: list[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
        if rows is not None and not isinstance(rows, list):
            raise DynamicPositionOptimizerError("rows must be a list when provided")
        candidates = rows or []
        output = [self._recommend_one(row) for row in candidates]
        return sorted(output, key=lambda item: (item["strategy_id"], item["market_regime"]))

    def _recommend_one(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, Mapping):
            raise DynamicPositionOptimizerError("each row must be a mapping")

        strategy_id = str(payload.get("strategy_id") or payload.get("strategy") or "UNKNOWN").strip() or "UNKNOWN"
        market_regime = str(payload.get("market_regime") or "UNKNOWN").strip().upper() or "UNKNOWN"
        strategy_grade = str(payload.get("strategy_grade") or payload.get("grade") or "SILVER").strip().upper() or "SILVER"

        expectancy = self._to_float(payload.get("expectancy", 0.0))
        profit_factor = self._to_float(payload.get("profit_factor", 0.0))
        drawdown = self._to_float(payload.get("drawdown", payload.get("max_drawdown", 0.0)))
        volatility = self._to_float(payload.get("volatility", 0.0))
        capital_utilization = self._to_float(payload.get("capital_utilization", 0.0))
        confidence = self._to_float(payload.get("confidence", 0.0))
        current_position_size = self._to_float(payload.get("current_position_size", payload.get("position_size", 0.0)))

        grade_multiplier = self._GRADE_MULTIPLIER.get(strategy_grade, 0.90)
        regime_multiplier = self._REGIME_MULTIPLIER.get(market_regime, self._REGIME_MULTIPLIER["UNKNOWN"])

        performance_signal = (0.45 * self._clamp01((expectancy + 1.0) / 2.0)) + (0.35 * self._clamp01(profit_factor / 2.0)) + (0.20 * self._clamp01(confidence))
        risk_signal = (0.45 * self._clamp01(drawdown)) + (0.35 * self._clamp01(volatility)) + (0.20 * self._clamp01(capital_utilization))
        net_signal = performance_signal - risk_signal

        suggested_position_size = current_position_size * grade_multiplier * regime_multiplier * (1.0 + (0.35 * net_signal))
        suggested_position_size = max(0.0, round(suggested_position_size, 8))

        if strategy_grade == "DISABLED" or suggested_position_size <= 0.0:
            action = "REDUCE"
            suggested_position_size = 0.0
        elif net_signal >= 0.12:
            action = "INCREASE"
        elif net_signal <= -0.08:
            action = "REDUCE"
        else:
            action = "KEEP"

        return {
            "strategy_id": strategy_id,
            "market_regime": market_regime,
            "strategy_grade": strategy_grade,
            "action": action,
            "suggested_position_size": suggested_position_size,
            "signals": {
                "performance_signal": round(performance_signal, 8),
                "risk_signal": round(risk_signal, 8),
                "net_signal": round(net_signal, 8),
            },
        }

    @staticmethod
    def _to_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _clamp01(value: float) -> float:
        return max(0.0, min(1.0, float(value)))
