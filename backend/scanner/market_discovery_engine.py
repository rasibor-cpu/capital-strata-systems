from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

import requests


COINBASE_PRODUCTS = "https://api.exchange.coinbase.com/products"
COINBASE_TICKER = "https://api.exchange.coinbase.com/products/{}/ticker"


class MarketDiscoveryEngine:
    """
    CSS Market Discovery Engine

    Dynamically finds the best tradable assets
    from the Coinbase market.

    Speed upgrades:
    - shared requests session
    - concurrent ticker fetches
    - capped worker pool
    - defensive JSON parsing

    Filters by:
    - USD pairs
    - liquidity
    """

    def __init__(self) -> None:
        self.min_volume_usd = 100000
        self.max_assets = 50

        # Concurrency tuning:
        # 12-20 is usually a good safe range for public REST endpoints.
        self.max_workers = 16

        # Timeouts kept modest so bad symbols do not stall the scan.
        self.products_timeout = 10
        self.ticker_timeout = 4

        # Shared HTTP session for connection reuse.
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "CSS-MarketDiscoveryEngine/1.0",
                "Accept": "application/json",
            }
        )

    def fetch_products(self) -> List[str]:
        try:
            response = self.session.get(COINBASE_PRODUCTS, timeout=self.products_timeout)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                return []
        except Exception:
            return []

        assets: List[str] = []

        for product in data:
            try:
                if product.get("quote_currency") != "USD":
                    continue

                if product.get("trading_disabled", False):
                    continue

                product_id = str(product.get("id", "")).strip()
                if not product_id:
                    continue

                assets.append(product_id)
            except Exception:
                continue

        return assets

    def fetch_ticker(self, product: str) -> Optional[Dict]:
        try:
            response = self.session.get(
                COINBASE_TICKER.format(product),
                timeout=self.ticker_timeout,
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                return None
            return data
        except Exception:
            return None

    def _score_product(self, product: str) -> Optional[Dict[str, float | str]]:
        ticker = self.fetch_ticker(product)
        if not ticker:
            return None

        try:
            volume = float(ticker.get("volume", 0) or 0)
            price = float(ticker.get("price", 0) or 0)
            liquidity = volume * price

            if liquidity < self.min_volume_usd:
                return None

            return {
                "symbol": product,
                "score": liquidity,
            }
        except Exception:
            return None

    def discover(self) -> List[str]:
        products = self.fetch_products()
        if not products:
            return []

        scored: List[Dict[str, float | str]] = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._score_product, product): product
                for product in products
            }

            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        scored.append(result)
                except Exception:
                    continue

        scored.sort(key=lambda x: float(x["score"]), reverse=True)
        return [str(item["symbol"]) for item in scored[: self.max_assets]]