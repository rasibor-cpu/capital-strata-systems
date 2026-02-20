"""
engine/regime/market_regime_model.py

Raw Market Regime Model (Pre-Smoothing)
Capital Strata Systems (CSS)

Purpose:
- Generate regime confidence scores from simple deterministic signals
- No smoothing here (handled by RegimeController)

Inputs expected:
- price_history (list of floats, newest last)
"""

from __future__ import annotations

from typing import List, Dict
import math

from engine.regime.regime_state import (
    TREND_UP,
    TREND_DOWN,
    RANGE,
    HIGH_VOLATILITY,
    LOW_VOLATILITY,
    normalize,
)


class MarketRegimeModel:

    def __init__(self) -> None:
        pass

    # ---------------------------------------------------------

    def evaluate(self, price_history: List[float]):

        if len(price_history) < 5:
            return normalize({RANGE: 1.0})

        returns = self._returns(price_history)

        momentum = self._momentum(returns)
        volatility = self._volatility(returns)

        conf: Dict[str, float] = {}

        # Trend detection
        if momentum > 0:
            conf[TREND_UP] = abs(momentum)
        elif momentum < 0:
            conf[TREND_DOWN] = abs(momentum)

        # Volatility detection
        if volatility > 0.015:
            conf[HIGH_VOLATILITY] = volatility
        else:
            conf[LOW_VOLATILITY] = 0.02

        # Range fallback
        if abs(momentum) < 0.002:
            conf[RANGE] = 0.5

        return normalize(conf)

    # ---------------------------------------------------------

    def _returns(self, prices: List[float]) -> List[float]:
        return [
            (prices[i] - prices[i - 1]) / prices[i - 1]
            for i in range(1, len(prices))
        ]

    # ---------------------------------------------------------

    def _momentum(self, returns: List[float]) -> float:
        return sum(returns[-5:]) / min(5, len(returns))

    # ---------------------------------------------------------

    def _volatility(self, returns: List[float]) -> float:
        if len(returns) < 2:
            return 0.0
        mean = sum(returns) / len(returns)
        var = sum((r - mean) ** 2 for r in returns) / len(returns)
        return math.sqrt(var)