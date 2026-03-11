from __future__ import annotations

from typing import List, Dict


class LiquidityVolatilityFilter:
    """
    Filters a large asset universe down to the most tradable assets.

    Ranking is based on:
    - liquidity (volume)
    - volatility (price movement)

    This dramatically reduces the workload for the AI scorer.
    """

    def __init__(
        self,
        max_assets: int = 30,
        min_volume: float = 100000,
        min_volatility: float = 0.002,
    ) -> None:
        self.max_assets = max_assets
        self.min_volume = min_volume
        self.min_volatility = min_volatility

    def filter(self, assets: List[Dict]) -> List[Dict]:
        """
        Filters and ranks assets.

        Expected asset structure:
        {
            "symbol": "BTC-USD",
            "volume": 1200000,
            "volatility": 0.015
        }
        """

        filtered = []

        for a in assets:

            volume = float(a.get("volume", 0))
            volatility = float(a.get("volatility", 0))

            if volume < self.min_volume:
                continue

            if volatility < self.min_volatility:
                continue

            score = (volume * volatility)

            a["lv_score"] = score
            filtered.append(a)

        filtered.sort(key=lambda x: x["lv_score"], reverse=True)

        return filtered[: self.max_assets]