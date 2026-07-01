from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


class QuantitativeAlphaEngine:
    """Advisory quantitative alpha scoring from internal performance data."""

    def evaluate(
        self,
        *,
        returns: Sequence[Any] | None = None,
        win_loss_history: Sequence[Any] | None = None,
        asset_class_pnl: Mapping[str, Any] | None = None,
        trade_expectancy: Any = None,
        volatility: Any = None,
        drawdown: Any = None,
        trend_stability: Any = None,
    ) -> dict[str, Any]:
        ret = self._numbers(returns)
        wins = self._win_loss(win_loss_history)
        pnl = asset_class_pnl if isinstance(asset_class_pnl, Mapping) else {}
        if not ret and not wins and not pnl and trade_expectancy is None:
            return self._unavailable("quantitative_alpha_inputs_unavailable")

        expectancy = self._float(trade_expectancy, self._avg(ret) if ret else 0.0)
        win_rate = sum(1 for value in wins if value > 0) / len(wins) if wins else (sum(1 for value in ret if value > 0) / len(ret) if ret else 0.5)
        vol = self._float(volatility, self._std(ret))
        dd = abs(self._float(drawdown, min(ret) if ret else 0.0))
        stability = self._float(trend_stability, 1.0 / (1.0 + vol))
        pnl_score = 50.0
        if pnl:
            values = [self._float(value, 0.0) for value in pnl.values()]
            pnl_score = 50.0 + max(-25.0, min(25.0, sum(values)))

        expectancy_score = max(0.0, min(100.0, 50.0 + expectancy * 5000.0))
        risk_adjusted = max(0.0, min(100.0, 50.0 + (expectancy / max(vol, 0.0001)) * 10.0))
        drawdown_penalty = min(40.0, dd * 100.0)
        regime_fit = max(0.0, min(100.0, stability * 100.0))
        alpha = int(round((expectancy_score * 0.3) + (risk_adjusted * 0.25) + (win_rate * 100.0 * 0.2) + (regime_fit * 0.15) + (pnl_score * 0.1) - drawdown_penalty))
        alpha = max(0, min(100, alpha))
        signal = "FAVORABLE" if alpha >= 65 else "UNFAVORABLE" if alpha <= 35 else "NEUTRAL"

        return {
            "status": "OK" if len(ret) >= 5 or wins else "PARTIAL",
            "alpha_score": alpha,
            "expectancy_score": round(expectancy_score, 6),
            "risk_adjusted_momentum": round(risk_adjusted, 6),
            "drawdown_penalty": round(drawdown_penalty, 6),
            "regime_fit_score": round(regime_fit, 6),
            "quantitative_signal": signal,
            "reasons": ["quantitative_inputs_available"],
            "advisory_only": True,
            "execution_allowed": False,
        }

    @staticmethod
    def _numbers(values: Sequence[Any] | None) -> list[float]:
        result: list[float] = []
        for value in values or []:
            try:
                result.append(float(value))
            except (TypeError, ValueError):
                continue
        return result

    @classmethod
    def _win_loss(cls, values: Sequence[Any] | None) -> list[float]:
        result: list[float] = []
        for row in values or []:
            if isinstance(row, Mapping):
                result.append(cls._float(row.get("pnl", row.get("realized_pnl", row.get("outcome", 0.0))), 0.0))
            else:
                result.append(cls._float(row, 0.0))
        return result

    @staticmethod
    def _float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _avg(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    @classmethod
    def _std(cls, values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean = cls._avg(values)
        return (sum((value - mean) ** 2 for value in values) / len(values)) ** 0.5

    @staticmethod
    def _unavailable(reason: str) -> dict[str, Any]:
        return {
            "status": "DATA UNAVAILABLE",
            "alpha_score": 0,
            "expectancy_score": 0,
            "risk_adjusted_momentum": 0,
            "drawdown_penalty": 0,
            "regime_fit_score": 0,
            "quantitative_signal": "DATA_UNAVAILABLE",
            "reasons": [reason],
            "advisory_only": True,
            "execution_allowed": False,
        }
