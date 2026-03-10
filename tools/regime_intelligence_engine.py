from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List
import statistics


@dataclass
class RegimeDecision:
    allow_trade: bool
    regime: str
    reason: str


class RegimeIntelligenceEngine:
    """
    CSS Institutional Regime Intelligence Engine

    Determines whether market conditions are favorable
    for mean-reversion trading.
    """

    def __init__(self) -> None:

        # Maximum allowed deviation from moving average
        self.max_trend_strength = 0.015

        # Maximum volatility band
        self.max_volatility = 0.03

        # Minimum acceptable liquidity
        self.min_liquidity = 0.0005

        # Momentum decay threshold
        self.momentum_decay_threshold = 0.002

    def evaluate(self, candles: List[Dict[str, Any]]) -> RegimeDecision:

        closes = [float(c["close"]) for c in candles]
        highs = [float(c["high"]) for c in candles]
        lows = [float(c["low"]) for c in candles]
        volumes = [float(c["volume"]) for c in candles]

        if len(closes) < 20:
            return RegimeDecision(False, "UNKNOWN", "Insufficient data")

        moving_average = statistics.mean(closes[-20:])

        trend_strength = abs(closes[-1] - moving_average) / moving_average

        volatility = (max(highs[-20:]) - min(lows[-20:])) / moving_average

        liquidity = statistics.mean(volumes[-10:])

        momentum = closes[-1] - closes[-5]

        if trend_strength > self.max_trend_strength:
            return RegimeDecision(
                False,
                "TRENDING",
                "Trend strength too high for mean-reversion",
            )

        if volatility > self.max_volatility:
            return RegimeDecision(
                False,
                "VOLATILE",
                "Volatility regime unstable",
            )

        if liquidity < self.min_liquidity:
            return RegimeDecision(
                False,
                "LOW_LIQUIDITY",
                "Liquidity insufficient",
            )

        if abs(momentum) > self.momentum_decay_threshold:
            return RegimeDecision(
                False,
                "MOMENTUM_ACTIVE",
                "Momentum still active",
            )

        return RegimeDecision(
            True,
            "MEAN_REVERSION_FAVORABLE",
            "Market regime favorable for mean-reversion trading",
        )