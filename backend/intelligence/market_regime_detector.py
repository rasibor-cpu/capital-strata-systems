from __future__ import annotations

from typing import Dict, List


class MarketRegimeDetector:
    """
    Detects market regime based on price behaviour.

    Possible regimes:
        MEAN_REVERSION
        TREND
        BREAKOUT
        UNSTABLE
    """

    def __init__(self):

        self.volatility_threshold = 0.025
        self.trend_threshold = 0.01
        self.breakout_threshold = 0.04

    def detect_regime(self, candles: List[Dict]) -> Dict:

        if not candles or len(candles) < 20:
            return {
                "regime": "UNSTABLE",
                "reason": "insufficient data",
                "confidence": 0.0,
            }

        closes = [float(c["close"]) for c in candles]

        last = closes[-1]
        prev = closes[-2]

        change = (last - prev) / prev

        volatility = self._compute_volatility(closes)

        trend_strength = abs((closes[-1] - closes[-20]) / closes[-20])

        if volatility > self.breakout_threshold:

            return {
                "regime": "BREAKOUT",
                "reason": "volatility spike",
                "confidence": volatility,
            }

        if trend_strength > self.trend_threshold:

            return {
                "regime": "TREND",
                "reason": "sustained directional move",
                "confidence": trend_strength,
            }

        if volatility < self.volatility_threshold:

            return {
                "regime": "MEAN_REVERSION",
                "reason": "low volatility range",
                "confidence": 1 - volatility,
            }

        return {
            "regime": "UNSTABLE",
            "reason": "mixed conditions",
            "confidence": 0.3,
        }

    def _compute_volatility(self, prices: List[float]) -> float:

        returns = []

        for i in range(1, len(prices)):
            returns.append((prices[i] - prices[i - 1]) / prices[i - 1])

        if not returns:
            return 0.0

        mean = sum(returns) / len(returns)

        variance = sum((r - mean) ** 2 for r in returns) / len(returns)

        return variance ** 0.5