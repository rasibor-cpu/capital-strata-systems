from __future__ import annotations

from typing import Dict, Any, List
import statistics


class AdaptiveExitEngine:
    """
    CSS Adaptive Exit Engine

    Determines when a profitable position should be exited
    based on reversal signals rather than fixed take-profit levels.
    """

    def __init__(self) -> None:

        self.momentum_reversal_threshold = 0.0015
        self.volatility_spike_threshold = 0.035
        self.vwap_reversion_threshold = 0.0008

    def evaluate_exit(
        self,
        entry_price: float,
        candles: List[Dict[str, Any]],
    ) -> Dict[str, Any]:

        closes = [float(c["close"]) for c in candles]
        highs = [float(c["high"]) for c in candles]
        lows = [float(c["low"]) for c in candles]

        last_price = closes[-1]

        profit = (last_price - entry_price) / entry_price

        ma20 = statistics.mean(closes[-20:])

        deviation_from_ma = abs((last_price - ma20) / ma20)

        volatility = (max(highs[-20:]) - min(lows[-20:])) / ma20

        momentum = closes[-1] - closes[-5]

        exit_conditions = {
            "momentum_reversal": abs(momentum) > self.momentum_reversal_threshold,
            "volatility_spike": volatility > self.volatility_spike_threshold,
            "vwap_reversion": deviation_from_ma < self.vwap_reversion_threshold,
        }

        exit_trade = any(exit_conditions.values())

        return {
            "exit_trade": exit_trade,
            "profit": round(profit, 6),
            "momentum": round(momentum, 6),
            "volatility": round(volatility, 6),
            "deviation_from_ma": round(deviation_from_ma, 6),
            "exit_conditions": exit_conditions,
        }


if __name__ == "__main__":

    sample_candles = [
        {"open": 1.08, "high": 1.081, "low": 1.079, "close": 1.0805}
    ] * 20

    engine = AdaptiveExitEngine()

    result = engine.evaluate_exit(
        entry_price=1.0790,
        candles=sample_candles,
    )

    print(result)