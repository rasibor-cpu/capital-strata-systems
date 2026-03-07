from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict
import random


@dataclass
class AssetScore:
    symbol: str
    liquidity_score: float
    volatility_score: float
    spread_score: float
    momentum_score: float
    total_score: float


class MarketIntelligenceEngine:
    """
    Phase 2 Market Intelligence Engine

    Responsibilities
    ----------------
    - Maintain tradable asset universe
    - Score assets
    - Rank assets
    - Return top tradable assets
    """

    def __init__(self, max_assets: int = 5):

        # universal multi-asset universe
        self.asset_universe = [

            # crypto
            "BTC-USD",
            "ETH-USD",
            "SOL-USD",
            "AVAX-USD",
            "LINK-USD",

            # FX
            "EUR-USD",
            "GBP-USD",
            "USD-JPY",
            "AUD-USD",
            "USD-CAD",
        ]

        self.max_assets = max_assets

    def score_asset(self, symbol: str) -> AssetScore:

        # Placeholder scoring logic (Phase 2 will improve)

        liquidity = random.uniform(6, 10)
        volatility = random.uniform(5, 10)
        spread = random.uniform(6, 10)
        momentum = random.uniform(4, 10)

        total = (
            liquidity * 0.30 +
            volatility * 0.25 +
            spread * 0.20 +
            momentum * 0.25
        )

        return AssetScore(
            symbol,
            liquidity,
            volatility,
            spread,
            momentum,
            total
        )

    def rank_assets(self) -> List[AssetScore]:

        scored_assets: List[AssetScore] = []

        for asset in self.asset_universe:
            scored_assets.append(self.score_asset(asset))

        ranked = sorted(
            scored_assets,
            key=lambda x: x.total_score,
            reverse=True
        )

        return ranked

    def get_top_assets(self) -> List[str]:

        ranked = self.rank_assets()

        top_assets = ranked[: self.max_assets]

        return [a.symbol for a in top_assets]


def demo():

    engine = MarketIntelligenceEngine(max_assets=5)

    ranked = engine.rank_assets()

    print("\nCSS Market Intelligence Ranking\n")

    for r in ranked:

        print(
            f"{r.symbol:10} "
            f"Liquidity:{r.liquidity_score:.2f} "
            f"Vol:{r.volatility_score:.2f} "
            f"Momentum:{r.momentum_score:.2f} "
            f"Total:{r.total_score:.2f}"
        )

    print("\nTop Assets:")

    print(engine.get_top_assets())


if __name__ == "__main__":

    demo()