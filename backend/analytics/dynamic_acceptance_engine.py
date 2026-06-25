from __future__ import annotations

from typing import Any


class DynamicAcceptanceEngineError(RuntimeError):
    """Fail-closed exception for dynamic acceptance threshold operations."""


class DynamicAcceptanceEngine:
    """Computes dynamic trade acceptance threshold using risk and performance context."""

    _REGIME_ADJUSTMENTS = {
        "TRENDING": -5.0,
        "BREAKOUT": -3.0,
        "RANGING": 2.0,
        "LOW_VOLATILITY": 1.5,
        "REVERSAL": 4.0,
        "HIGH_VOLATILITY": 6.0,
        "UNKNOWN": 8.0,
    }

    def resolve_threshold(
        self,
        *,
        market_regime: str,
        volatility: float,
        drawdown: float,
        recent_performance: float,
        concentration_risk: float,
        base_threshold: float = 65.0,
    ) -> dict[str, Any]:
        regime = str(market_regime or "").strip().upper()
        if not regime:
            raise DynamicAcceptanceEngineError("market_regime must be non-empty")

        base = self._to_float(base_threshold, "base_threshold")
        volatility_value = self._fraction(volatility, "volatility")
        drawdown_value = self._drawdown_fraction(drawdown)
        concentration_value = self._fraction(concentration_risk, "concentration_risk")
        performance_value = self._performance(recent_performance)

        threshold = base
        threshold += self._REGIME_ADJUSTMENTS.get(regime, self._REGIME_ADJUSTMENTS["UNKNOWN"])
        threshold += volatility_value * 20.0
        threshold += drawdown_value * 25.0
        threshold += concentration_value * 20.0
        threshold += max(0.0, -performance_value) * 18.0
        threshold -= max(0.0, performance_value) * 8.0
        threshold = round(max(0.0, min(100.0, threshold)), 8)

        return {
            "threshold": threshold,
            "market_regime": regime,
            "diagnostics": {
                "base_threshold": base,
                "volatility": volatility_value,
                "drawdown": drawdown_value,
                "recent_performance": performance_value,
                "concentration_risk": concentration_value,
            },
        }

    @staticmethod
    def _to_float(value: Any, field_name: str) -> float:
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise DynamicAcceptanceEngineError(f"{field_name} must be numeric") from exc

    @staticmethod
    def _fraction(value: Any, field_name: str) -> float:
        numeric = DynamicAcceptanceEngine._to_float(value, field_name)
        if numeric < 0.0 or numeric > 1.0:
            raise DynamicAcceptanceEngineError(f"{field_name} must be between 0 and 1")
        return numeric

    @staticmethod
    def _drawdown_fraction(value: Any) -> float:
        numeric = DynamicAcceptanceEngine._to_float(value, "drawdown")
        magnitude = abs(numeric)
        if magnitude > 1.0:
            raise DynamicAcceptanceEngineError("drawdown magnitude must be between 0 and 1")
        return magnitude

    @staticmethod
    def _performance(value: Any) -> float:
        numeric = DynamicAcceptanceEngine._to_float(value, "recent_performance")
        if numeric < -1.0 or numeric > 1.0:
            raise DynamicAcceptanceEngineError("recent_performance must be between -1 and 1")
        return numeric
