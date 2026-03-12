from __future__ import annotations

import requests
from typing import List


COINBASE_PRODUCTS = "https://api.exchange.coinbase.com/products"
COINBASE_TICKER = "https://api.exchange.coinbase.com/products/{}/ticker"


class MarketDiscoveryEngine:

    def __init__(self):

        self.min_volume_usd = 1_000_000
        self.max_assets = 12
        self.scan_limit = 60

    def fetch_products(self) -> List[str]:

        try:
            r = requests.get(COINBASE_PRODUCTS, timeout=10)
            data = r.json()
        except Exception:
            return []

        assets = []

        for p in data:

            if p.get("quote_currency") != "USD":
                continue

            if p.get("trading_disabled"):
                continue

            assets.append(p["id"])

        # only examine first N markets to keep scanning fast
        return assets[: self.scan_limit]

    def fetch_ticker(self, product: str):

        try:
            r = requests.get(
                COINBASE_TICKER.format(product),
                timeout=5,
            )
            return r.json()
        except Exception:
            return {}

    def score_asset(self, product: str):

        ticker = self.fetch_ticker(product)

        try:
            price = float(ticker.get("price", 0))
            volume = float(ticker.get("volume", 0))
        except Exception:
            return 0

        if price <= 0 or volume <= 0:
            return 0

        volume_usd = price * volume

        if volume_usd < self.min_volume_usd:
            return 0

        return volume_usd

    def get_top_universe(self):

        products = self.fetch_products()

        scored = []

        for p in products:

            score = self.score_asset(p)

            if score <= 0:
                continue

            scored.append((p, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        return [p for p, _ in scored[: self.max_assets]]


def get_top_universe(max_assets: int = 12):

    engine = MarketDiscoveryEngine()
    engine.max_assets = max_assets

    return engine.get_top_universe()


if __name__ == "__main__":

    print("\nTop CSS tradable universe:\n")

    universe = get_top_universe()

    for a in universe:
        print(a)