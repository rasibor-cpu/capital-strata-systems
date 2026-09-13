from __future__ import annotations

import os
from decimal import Decimal, InvalidOperation
from threading import Lock


class PriceFeed:
    """Fail-closed price-feed compatibility boundary.

    The historical dashboard imports this module at startup. The cloud branch
    was missing the module entirely, preventing test collection. This
    implementation deliberately does NOT add live market connectivity.

    In SIMULATED/TEST mode callers may inject deterministic prices with
    set_simulated_price. Otherwise get_price returns None so the caller must
    treat price availability explicitly.
    """

    def __init__(self, provider: str | None = None):
        self.provider = str(provider or os.getenv("DATA_PROVIDER", "UNAVAILABLE")).upper()
        self._prices: dict[str, Decimal] = {}
        self._lock = Lock()

    @property
    def live_network_enabled(self) -> bool:
        return False

    def set_simulated_price(self, symbol: str, price: Decimal | float | int | str) -> None:
        if self.provider not in {"SIMULATED", "TEST"} and os.getenv("CSS_TEST_MODE") != "1":
            raise RuntimeError("simulated price injection is disabled outside simulated/test mode")
        normalized_symbol = str(symbol or "").strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol is required")
        try:
            value = Decimal(str(price))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("price must be numeric") from exc
        if value <= Decimal("0"):
            raise ValueError("price must be positive")
        with self._lock:
            self._prices[normalized_symbol] = value

    def get_price(self, symbol: str) -> float | None:
        normalized_symbol = str(symbol or "").strip().upper()
        if not normalized_symbol:
            return None
        with self._lock:
            value = self._prices.get(normalized_symbol)
        return float(value) if value is not None else None


_feed: PriceFeed | None = None
_feed_lock = Lock()


def get_price_feed() -> PriceFeed:
    global _feed
    with _feed_lock:
        if _feed is None:
            _feed = PriceFeed()
        return _feed
