from __future__ import annotations

from typing import List, Dict


class LiquidityVolatilityFilter:
    """
    CSS Institutional Liquidity / Volatility Filter

    Purpose
    -------
    Reduce the trading universe to assets that are realistically tradable.

    Institutional filters applied:
        • Minimum liquidity requirement
        • Acceptable volatility band
        • Composite tradability score

    Result:
        Only the highest quality markets reach the AI opportunity scorer.
    """

    def __init__(
        self,
        max_assets: int = 20,
        min_volume: float = 500000,
        min_volatility: float = 0.001,
        max_volatility: float = 0.08,
    ) -> None:

        self.max_assets = max_assets
        self.min_volume = min_volume
        self.min_volatility = min_volatility
        self.max_volatility = max_volatility

    def filter(self, assets: List[Dict]) -> List[Dict]:

        filtered: List[Dict] = []

        for asset in assets:

            symbol = asset.get("symbol", "UNKNOWN")

            volume = float(asset.get("volume", 0))
            volatility = float(asset.get("volatility", 0))

            # --------------------------------------------------
            # HARD FILTERS
            # --------------------------------------------------

            if volume < self.min_volume:
                continue

            if volatility < self.min_volatility:
                continue

            if volatility > self.max_volatility:
                continue

            # --------------------------------------------------
            # TRADABILITY SCORE
            # --------------------------------------------------

            liquidity_score = volume ** 0.5
            volatility_score = volatility * 100

            score = liquidity_score * volatility_score

            asset["lv_score"] = score

            filtered.append(asset)

        # --------------------------------------------------
        # SORT BY TRADABILITY
        # --------------------------------------------------

        filtered.sort(key=lambda x: x["lv_score"], reverse=True)

        return filtered[: self.max_assets]