from __future__ import annotations

from typing import Any, Dict, List, Optional
import requests


class MarketDiscoveryEngine:
    """
    CSS Broker-Agnostic Market Discovery Engine

    Purpose
    -------
    - discover tradable instruments from a broker/venue
    - score them consistently
    - return the strongest candidates for downstream CSS logic

    Design
    ------
    - broker-agnostic outer interface
    - broker-specific fetch methods contained internally
    - current implementation: Coinbase spot crypto
    - future implementations can extend for OANDA, Alpaca, Questrade, etc.
    """

    def __init__(
        self,
        *,
        provider: str = "coinbase",
        min_volume_usd: float = 250_000,
        max_assets: int = 60,
        scan_limit: int = 250,
        request_timeout_products: int = 10,
        request_timeout_ticker: int = 5,
    ) -> None:
        self.provider = str(provider).strip().lower()
        self.min_volume_usd = float(min_volume_usd)
        self.max_assets = int(max_assets)
        self.scan_limit = int(scan_limit)
        self.request_timeout_products = int(request_timeout_products)
        self.request_timeout_ticker = int(request_timeout_ticker)

        # Coinbase defaults
        self.coinbase_products_url = "https://api.exchange.coinbase.com/products"
        self.coinbase_ticker_url = "https://api.exchange.coinbase.com/products/{}/ticker"

    # ---------------------------------------------------------
    # PUBLIC API
    # ---------------------------------------------------------
    def get_top_universe(self) -> List[str]:
        products = self.fetch_products()

        scored: List[tuple[str, float]] = []

        for product in products:
            score = self.score_asset(product)
            if score <= 0:
                continue
            scored.append((product, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        return [product for product, _ in scored[: self.max_assets]]

    # ---------------------------------------------------------
    # BROKER-AGNOSTIC ROUTERS
    # ---------------------------------------------------------
    def fetch_products(self) -> List[str]:
        if self.provider == "coinbase":
            return self._fetch_coinbase_products()

        # Placeholder for future brokers
        return []

    def fetch_ticker(self, product: str) -> Dict[str, Any]:
        if self.provider == "coinbase":
            return self._fetch_coinbase_ticker(product)

        # Placeholder for future brokers
        return {}

    def score_asset(self, product: str) -> float:
        """
        Generic scoring model for liquid tradable instruments.

        Current implementation assumes:
        - instrument has a live price
        - instrument has a measurable recent volume
        - score proxy = approximate dollar turnover

        This is suitable for Coinbase spot markets now,
        and can be replaced/extended per broker later.
        """
        ticker = self.fetch_ticker(product)

        try:
            price = float(ticker.get("price", 0) or 0)
            volume = float(ticker.get("volume", 0) or 0)
        except Exception:
            return 0.0

        if price <= 0 or volume <= 0:
            return 0.0

        volume_usd = price * volume

        if volume_usd < self.min_volume_usd:
            return 0.0

        return float(volume_usd)

    # ---------------------------------------------------------
    # COINBASE IMPLEMENTATION
    # ---------------------------------------------------------
    def _fetch_coinbase_products(self) -> List[str]:
        try:
            response = requests.get(
                self.coinbase_products_url,
                timeout=self.request_timeout_products,
            )
            response.raise_for_status()
            data = response.json()
        except Exception:
            return []

        assets: List[str] = []
        seen = set()

        for product in data:
            try:
                product_id = str(product.get("id", "")).strip().upper()
                quote_currency = str(product.get("quote_currency", "")).strip().upper()
                trading_disabled = bool(product.get("trading_disabled", False))

                if not product_id:
                    continue

                if quote_currency != "USD":
                    continue

                if trading_disabled:
                    continue

                if product_id in seen:
                    continue

                seen.add(product_id)
                assets.append(product_id)

            except Exception:
                continue

        return assets[: self.scan_limit]

    def _fetch_coinbase_ticker(self, product: str) -> Dict[str, Any]:
        try:
            response = requests.get(
                self.coinbase_ticker_url.format(product),
                timeout=self.request_timeout_ticker,
            )
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict):
                return payload
            return {}
        except Exception:
            return {}


def get_top_universe(
    max_assets: int = 60,
    *,
    provider: str = "coinbase",
    min_volume_usd: float = 250_000,
    scan_limit: int = 250,
) -> List[str]:
    engine = MarketDiscoveryEngine(
        provider=provider,
        min_volume_usd=min_volume_usd,
        max_assets=max_assets,
        scan_limit=scan_limit,
    )
    return engine.get_top_universe()


if __name__ == "__main__":
    print("\nTop CSS tradable universe:\n")
    universe = get_top_universe()

    for asset in universe:
        print(asset)