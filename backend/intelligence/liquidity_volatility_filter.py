from __future__ import annotations

from typing import Dict, List


class LiquidityVolatilityFilter:
    """
    CSS Institutional Liquidity / Volatility Filter

    Purpose
    -------
    Reduce the trading universe to assets that are realistically tradable.

    Filters applied:
        • minimum liquidity
        • acceptable volatility band
        • minimum price floor
        • composite tradability score

    This version is intentionally stricter so micro-priced symbols do not
    dominate the shortlist merely because they are noisy.
    """

    def __init__(
        self,
        max_assets: int = 20,
        min_volume: float = 500000.0,
        min_volatility: float = 0.001,
        max_volatility: float = 0.08,
        min_price: float = 0.05,
    ) -> None:
        self.max_assets = max_assets
        self.min_volume = min_volume
        self.min_volatility = min_volatility
        self.max_volatility = max_volatility
        self.min_price = min_price

    def filter(self, assets: List[Dict]) -> List[Dict]:
        filtered: List[Dict] = []

        for asset in assets:
            symbol = str(asset.get("symbol", "UNKNOWN"))
            volume = float(asset.get("volume", 0.0))
            volatility = float(asset.get("volatility", 0.0))
            price = self._extract_price(asset)

            # --------------------------------------------------
            # HARD FILTERS
            # --------------------------------------------------

            if price < self.min_price:
                continue

            if volume < self.min_volume:
                continue

            if volatility < self.min_volatility:
                continue

            if volatility > self.max_volatility:
                continue

            # --------------------------------------------------
            # TRADABILITY SCORE
            # Higher liquidity helps, but extreme volatility is moderated.
            # --------------------------------------------------

            liquidity_score = volume ** 0.5
            volatility_score = volatility * 100.0

            # Prefer assets with meaningful price level
            price_score = min(price, 500.0) ** 0.25

            score = liquidity_score * volatility_score * price_score

            item = dict(asset)
            item["lv_score"] = score
            filtered.append(item)

        filtered.sort(key=lambda x: x["lv_score"], reverse=True)
        return filtered[: self.max_assets]

    @staticmethod
    def _extract_price(asset: Dict) -> float:
        for key in ("mid", "price", "close", "last", "last_price"):
            value = asset.get(key)
            try:
                if value is not None:
                    return float(value)
            except (TypeError, ValueError):
                pass
        return 0.0