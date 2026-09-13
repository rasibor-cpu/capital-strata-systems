from __future__ import annotations

import os
from decimal import Decimal, InvalidOperation
from threading import Lock
from typing import Any, Optional

try:
    import requests
except Exception:  # pragma: no cover
    requests = None


class PriceFeed:
    """Read-only price-feed boundary with deterministic test injection.

    Production behavior preserves the existing public Coinbase spot-price
    lookup used by legacy MTM paths. In SIMULATED/TEST mode, callers may inject
    deterministic prices without network access.

    This class has no broker execution or money-movement authority.
    """

    def __init__(self, provider: str | None = None) -> None:
        self.provider = str(
            provider or os.getenv("DATA_PROVIDER", "COINBASE_PUBLIC")
        ).strip().upper()

        self.timeout_seconds = float(
            os.getenv("CSS_PRICE_FEED_TIMEOUT_SECONDS", "4") or 4
        )

        self._last_prices: dict[str, float] = {}
        self._simulated_prices: dict[str, Decimal] = {}
        self._lock = Lock()

    @property
    def live_network_enabled(self) -> bool:
        return (
            self.provider not in {"SIMULATED", "TEST", "UNAVAILABLE"}
            and os.getenv("CSS_TEST_MODE") != "1"
            and requests is not None
        )

    def _normalize_symbol(self, symbol: str) -> str:
        return str(symbol or "").strip().upper().replace("_", "-")

    def set_simulated_price(
        self,
        symbol: str,
        price: Decimal | float | int | str,
    ) -> None:
        if (
            self.provider not in {"SIMULATED", "TEST"}
            and os.getenv("CSS_TEST_MODE") != "1"
        ):
            raise RuntimeError(
                "simulated price injection is disabled outside simulated/test mode"
            )

        normalized_symbol = self._normalize_symbol(symbol)
        if not normalized_symbol:
            raise ValueError("symbol is required")

        try:
            value = Decimal(str(price))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("price must be numeric") from exc

        if value <= Decimal("0"):
            raise ValueError("price must be positive")

        with self._lock:
            self._simulated_prices[normalized_symbol] = value

    def _simulated_price(self, symbol: str) -> Optional[float]:
        with self._lock:
            value = self._simulated_prices.get(symbol)
        return float(value) if value is not None else None

    def _coinbase_public_price(self, symbol: str) -> Optional[float]:
        if not self.live_network_enabled:
            return None

        product_id = self._normalize_symbol(symbol)
        if "-" not in product_id:
            return None

        url = (
            "https://api.exchange.coinbase.com/products/"
            f"{product_id}/ticker"
        )

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

            with self._lock:
                self._last_prices[product_id] = parsed

            return parsed

        except Exception:
            return None

    def get_price(self, symbol: str) -> Optional[float]:
        key = self._normalize_symbol(symbol)

        if not key:
            return None

        injected = self._simulated_price(key)
        if injected is not None:
            return injected

        if self.provider in {"SIMULATED", "TEST", "UNAVAILABLE"}:
            return None

        price = self._coinbase_public_price(key)
        if price is not None:
            return price

        with self._lock:
            return self._last_prices.get(key)


_feed: PriceFeed | None = None
_feed_lock = Lock()


def get_price_feed() -> PriceFeed:
    global _feed

    with _feed_lock:
        if _feed is None:
            _feed = PriceFeed()

        return _feed
