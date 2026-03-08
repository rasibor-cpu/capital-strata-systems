"""
Capital Strata Systems (CSS)
Coinbase Broker Adapter

Provides a thin adapter for pulling market data and (optionally)
submitting orders to Coinbase. Designed so the execution layer
can be swapped for other brokers later.

Current scope:
- Public candles endpoint (no auth required)
- Basic account/order placeholders
"""

from __future__ import annotations

import requests
from typing import Any, Dict, List, Optional


COINBASE_CANDLES_URL = "https://api.exchange.coinbase.com/products/{product_id}/candles"


# Map CSS granularity names to Coinbase seconds
GRANULARITY_MAP = {
    "ONE_MINUTE": 60,
    "FIVE_MINUTE": 300,
    "FIFTEEN_MINUTE": 900,
    "ONE_HOUR": 3600,
    "SIX_HOUR": 21600,
    "ONE_DAY": 86400,
}


class CoinbaseAdapter:
    def __init__(
        self,
        *,
        api_key_name: str = "",
        api_private_key_path: str = "",
        paper_mode: bool = True,
        timeout_seconds: int = 10,
    ) -> None:
        self.api_key_name = api_key_name
        self.api_private_key_path = api_private_key_path
        self.paper_mode = paper_mode
        self.timeout_seconds = timeout_seconds

    # ---------- Market Data ----------

    def get_candles(
        self,
        product_id: str,
        granularity_name: str,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """
        Fetch recent candles from Coinbase public API.

        Coinbase returns:
        [ time, low, high, open, close, volume ]
        """

        granularity = GRANULARITY_MAP.get(granularity_name)
        if granularity is None:
            raise ValueError(f"Unsupported granularity: {granularity_name}")

        url = COINBASE_CANDLES_URL.format(product_id=product_id)

        params = {
            "granularity": granularity,
        }

        resp = requests.get(url, params=params, timeout=self.timeout_seconds)
        resp.raise_for_status()

        raw = resp.json()

        # Coinbase returns newest first; reverse to oldest→newest
        raw.reverse()

        candles: List[Dict[str, Any]] = []

        for item in raw[-limit:]:
            ts, low, high, open_, close, volume = item

            candles.append(
                {
                    "ts": ts,
                    "low": float(low),
                    "high": float(high),
                    "open": float(open_),
                    "close": float(close),
                    "volume": float(volume),
                }
            )

        return candles

    # ---------- Execution (placeholder) ----------

    def place_market_buy(
        self,
        *,
        product_id: str,
        size_usd: float,
    ) -> Dict[str, Any]:
        """
        Placeholder for market buy.
        Currently returns simulated order response.
        """

        if self.paper_mode:
            return {
                "status": "paper_filled",
                "product_id": product_id,
                "size_usd": size_usd,
            }

        raise NotImplementedError(
            "Live Coinbase execution not yet enabled in adapter."
        )

    def place_market_sell(
        self,
        *,
        product_id: str,
        size_asset: float,
    ) -> Dict[str, Any]:
        """
        Placeholder for market sell.
        """

        if self.paper_mode:
            return {
                "status": "paper_filled",
                "product_id": product_id,
                "size_asset": size_asset,
            }

        raise NotImplementedError(
            "Live Coinbase execution not yet enabled in adapter."
        )

    # ---------- Account ----------

    def get_account(self) -> Dict[str, Any]:
        """
        Placeholder account info.
        """

        if self.paper_mode:
            return {
                "mode": "paper",
                "balance_usd": 0.0,
            }

        raise NotImplementedError(
            "Live account query not yet enabled in adapter."
        )