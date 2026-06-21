from __future__ import annotations

import os
from typing import Any, Optional

try:
    import requests
except Exception:  # pragma: no cover
    requests = None


class PriceFeed:
    """
    CSS Phase 3A Price Feed

    Purpose
    -------
    Provide real/public market prices for paper/live dashboard MTM.

    Current coverage:
    - Coinbase spot crypto via public Coinbase Exchange ticker endpoint.
    - FX/options/futures return None unless later adapters are added.

    PCNRASS rules:
    - Never places orders.
    - Never requires private keys for public spot prices.
    - Never fabricates random drift.
    - Uses last known price only as a continuity fallback for the same symbol.
    """

    def __init__(self) -> None:
        self.timeout_seconds = float(os.getenv("CSS_PRICE_FEED_TIMEOUT_SECONDS", "4") or 4)
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

            px = float(price)
            if px <= 0:
                return None

            self._last_prices[product_id] = px
            return px
        except Exception:
            return None

    def get_price(self, symbol: str) -> Optional[float]:
        key = self._normalize_coinbase_symbol(symbol)

        # Coinbase spot symbols are formatted like BTC-USD.
        if "-" in key:
            px = self._coinbase_public_price(key)
            if px is not None:
                return px

        return self._last_prices.get(key)


_price_feed = PriceFeed()


def get_price_feed() -> PriceFeed:
    return _price_feed
