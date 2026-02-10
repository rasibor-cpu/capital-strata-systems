from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class MarketSnapshot:
    """
    Minimal market snapshot for Phase 2.

    This stays adapter-agnostic and lets us plug in:
    - Alpaca paper
    - OANDA practice
    - CSV replay
    - Yahoo Finance
    - Crypto exchanges

    For now: we support a stub "SIM" provider.
    """
    symbol: str
    timestamp_utc: str
    price: float
    source: str
    meta: Dict[str, Any]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DataProvider:
    """
    Abstract interface for data providers.
    """
    def get_snapshot(self, symbol: str) -> MarketSnapshot:
        raise NotImplementedError


class SimDataProvider(DataProvider):
    """
    Safe stub provider. Generates a deterministic pseudo-price.

    Why:
    - Lets engine tick run with "real" objects today.
    - Keeps execution locked.
    - Avoids broker wiring until BROKER phase.
    """
    def __init__(self) -> None:
        self._t = 0

    def get_snapshot(self, symbol: str) -> MarketSnapshot:
        self._t += 1
        # Simple deterministic wave (not random)
        base = 100.0
        price = base + (self._t % 10) * 0.25

        return MarketSnapshot(
            symbol=symbol,
            timestamp_utc=utc_now_iso(),
            price=float(price),
            source="SIM",
            meta={"t": self._t},
        )


def get_default_provider() -> DataProvider:
    """
    Phase 2 default.
    Later we will switch based on env:
    - DATA_PROVIDER=ALPACA
    - DATA_PROVIDER=OANDA
    - DATA_PROVIDER=CSV
    """
    return SimDataProvider()
