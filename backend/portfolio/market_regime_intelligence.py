from __future__ import annotations

from typing import Any, Iterable, Mapping

from backend.portfolio.constants import (
    REGIME_CORRELATION_STRESS,
    REGIME_HIGH_VOLATILITY,
    REGIME_LOW_VOLATILITY,
    REGIME_RANGING,
    REGIME_TRENDING_DOWN,
    REGIME_TRENDING_UP,
    REGIME_UNKNOWN,
)
from backend.portfolio.quantitative_metrics_engine import QuantitativeMetricsEngine
from backend.portfolio.utils import safe_series


class MarketRegimeIntelligenceError(RuntimeError):
    """Fail-closed exception for market regime intelligence."""


class MarketRegimeIntelligence:
    """Richer deterministic market regime detection from simple series inputs."""

    def detect(
        self,
        prices: Iterable[Any] | None = None,
        returns: Iterable[Any] | None = None,
        volatility: Iterable[Any] | None = None,
        correlation_matrix: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return_series = safe_series(returns)
        if len(return_series) < 3:
            price_series = safe_series(prices)
            return_series = self._returns_from_prices(price_series)
        if len(return_series) < 3:
            return self._unknown("return_series_insufficient")

        volatility_series = safe_series(volatility)
        realized_volatility = (
            sum(volatility_series) / len(volatility_series)
            if volatility_series
            else QuantitativeMetricsEngine()._stddev(return_series)
        )
        total_return = sum(return_series)
        positive_rate = sum(1 for value in return_series if value > 0.0) / len(return_series)
        average_correlation = self._average_abs_correlation(correlation_matrix)

        volatility_state = "HIGH" if realized_volatility >= 0.04 else ("LOW" if realized_volatility <= 0.008 else "NORMAL")
        if total_return > 0.03 and positive_rate >= 0.60:
            trend_state = "UP"
        elif total_return < -0.03 and positive_rate <= 0.40:
            trend_state = "DOWN"
        else:
            trend_state = "RANGING"
        correlation_state = "STRESS" if average_correlation >= 0.75 else ("ELEVATED" if average_correlation >= 0.55 else "NORMAL")

        reasons: list[str] = []
        if correlation_state == "STRESS":
            regime = REGIME_CORRELATION_STRESS
            risk_bias = "DEFENSIVE"
            confidence = 85
            reasons.append("Average absolute correlation is stressed.")
        elif volatility_state == "HIGH":
            regime = REGIME_HIGH_VOLATILITY
            risk_bias = "DEFENSIVE"
            confidence = 80
            reasons.append("Realized volatility is high.")
        elif trend_state == "UP":
            regime = REGIME_TRENDING_UP
            risk_bias = "OPPORTUNISTIC"
            confidence = 75
            reasons.append("Returns show positive trend persistence.")
        elif trend_state == "DOWN":
            regime = REGIME_TRENDING_DOWN
            risk_bias = "DEFENSIVE"
            confidence = 75
            reasons.append("Returns show negative trend persistence.")
        elif volatility_state == "LOW":
            regime = REGIME_LOW_VOLATILITY
            risk_bias = "BALANCED"
            confidence = 70
            reasons.append("Realized volatility is low.")
        else:
            regime = REGIME_RANGING
            risk_bias = "BALANCED"
            confidence = 65
            reasons.append("Returns are range-bound without strong trend.")

        return {
            "status": "OK",
            "detected_regime": regime,
            "confidence": confidence,
            "volatility_state": volatility_state,
            "trend_state": trend_state,
            "correlation_state": correlation_state,
            "risk_bias": risk_bias,
            "reasons": reasons,
            "advisory_only": True,
        }

    @staticmethod
    def _returns_from_prices(prices: list[float]) -> list[float]:
        if len(prices) < 4:
            return []
        returns = []
        for previous, current in zip(prices, prices[1:]):
            if previous == 0.0:
                continue
            returns.append((current - previous) / previous)
        return returns

    @staticmethod
    def _average_abs_correlation(matrix: Mapping[str, Mapping[str, Any]] | None) -> float:
        if not isinstance(matrix, Mapping):
            return 0.0
        values = []
        for left, row in matrix.items():
            if not isinstance(row, Mapping):
                continue
            for right, value in row.items():
                if str(left) >= str(right):
                    continue
                try:
                    values.append(abs(float(value)))
                except (TypeError, ValueError):
                    continue
        return sum(values) / len(values) if values else 0.0

    @staticmethod
    def _unknown(reason: str) -> dict[str, Any]:
        return {
            "status": "DATA UNAVAILABLE",
            "detected_regime": REGIME_UNKNOWN,
            "confidence": 0,
            "volatility_state": REGIME_UNKNOWN,
            "trend_state": REGIME_UNKNOWN,
            "correlation_state": REGIME_UNKNOWN,
            "risk_bias": "DEFENSIVE",
            "reasons": [reason],
            "advisory_only": True,
        }
