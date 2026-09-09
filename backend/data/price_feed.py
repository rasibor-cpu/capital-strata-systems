from __future__ import annotations

import os
from typing import Any, Optional

try:
    import requests
except Exception:  # pragma: no cover
    requests = None


class PriceFeed:
    """Read-only public Coinbase spot price feed used by legacy MTM paths."""

    def __init__(self) -> None:
        self.timeout_seconds = float(
            os.getenv("CSS_PRICE_FEED_TIMEOUT_SECONDS", "4") or 4
        )
        self._last_prices: dict[str, float] = {}

    def _normalize_coinbase_symbol(self, symbol: str) -> str:
        return str(symbol or "").strip().upper().replace("_", "-")

    def _coinbase_public_price(self, symbol: str) -> Optional[float]:
        if requests is None:
            return None
        product_id = self._normalize_coinbase_symbol(symbol)
        if "-" not in product_id:
            return None
        url = f"https://api.exchange.coinbase.com/products/{product_id}/ticker"
        try:
            response = requests.get(
                url,
                timeout=self.timeout_seconds,
                headers={"User-Agent": "CSS-PriceFeed/Phase3A"},
            )
            if response.status_code != 200:
                return None
            data: dict[str, Any] = response.json()
            price = data.get("price")
            if price is None:
                return None
            parsed = float(price)
            if parsed <= 0:
                return None
            self._last_prices[product_id] = parsed
            return parsed
        except Exception:
            return None

    def get_price(self, symbol: str) -> Optional[float]:
        key = self._normalize_coinbase_symbol(symbol)
        if "-" in key:
            price = self._coinbase_public_price(key)
            if price is not None:
                return price
        return self._last_prices.get(key)


_price_feed = PriceFeed()


def get_price_feed() -> PriceFeed:
    return _price_feed