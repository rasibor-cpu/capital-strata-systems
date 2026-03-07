from __future__ import annotations

from dataclasses import dataclass
from typing import Dict
import random


@dataclass
class StrategyDecision:
    asset: str
    regime: str
    strategy: str


class StrategySelector:
    """
    Phase 2 Strategy Intelligence Engine

    Determines the best strategy for each asset
    based on the detected market regime.
    """

    def __init__(self):

        self.regime_strategies: Dict[str, str] = {

            "TREND": "trend_following",
            "RANGE": "vwap_mean_reversion",
            "VOLATILE": "volatility_breakout",
        }

    def detect_market_regime(self, asset: str) -> str:
        """
        Placeholder regime detection.
        Later versions will use real market data.
        """

        regimes = ["TREND", "RANGE", "VOLATILE"]

        return random.choice(regimes)

    def select_strategy(self, asset: str) -> StrategyDecision:

        regime = self.detect_market_regime(asset)

        strategy = self.regime_strategies[regime]

        return StrategyDecision(
            asset=asset,
            regime=regime,
            strategy=strategy
        )


def demo():

    selector = StrategySelector()

    assets = [
        "BTC-USD",
        "ETH-USD",
        "SOL-USD",
        "EUR-USD",
        "GBP-USD"
    ]

    print("\nCSS Strategy Selection\n")

    for asset in assets:

        decision = selector.select_strategy(asset)

        print(
            f"{decision.asset:10} "
            f"Regime:{decision.regime:10} "
            f"Strategy:{decision.strategy}"
        )


if __name__ == "__main__":

    demo()