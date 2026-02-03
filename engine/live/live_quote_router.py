"""
REA Capital Trading Engine
Live Quote Router (READ-ONLY)

Branch: live-adapters
Purpose:
- Provide a standardized quote snapshot from any live adapter
- Adapter-agnostic: TwelveData, Alpaca, others
- No execution. No orders. No positions.

Constitutional Alignment:
- Supports Layer 1 (Market Reality) by normalizing symbols
- Supports Layer 5 (Execution Control) by providing quote freshness
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, Dict
import time


# -----------------------------
# Standardized Quote Snapshot
# -----------------------------
@dataclass(frozen=True)
class QuoteSnapshot:
    source: str
    symbol: str                 # broker symbol (adapter output)
    rea_instrument: str         # REA canonical instrument name
    bid: Optional[float]
    ask: Optional[float]
    mid: Optional[float]
    spread: Optional[float]
    quote_age_ms: int
    timestamp: float


# -----------------------------
# Adapter Protocol (Read-Only)
# -----------------------------
class QuoteAdapter(Protocol):
    name: str

    def get_quote(self, symbol: str) -> Dict:
        """
        Returns a dict with at least:
          - bid (optional)
          - ask (optional)
          - mid (optional)
          - timestamp (optional, epoch seconds)
        """
        ...


# -----------------------------
# Router
# -----------------------------
class LiveQuoteRouter:
    """
    Converts raw adapter output into a standardized QuoteSnapshot.
    """

    def __init__(self, adapter: QuoteAdapter, mapping: Dict[str, str]):
        """
        mapping: { rea_instrument: broker_symbol }
        """
        self.adapter = adapter
        self.mapping = mapping

    def get_snapshot(self, rea_instrument: str) -> QuoteSnapshot:
        ts_now = time.time()

        if rea_instrument not in self.mapping:
            raise KeyError(
                f"Missing broker mapping for REA instrument: {rea_instrument}"
            )

        broker_symbol = self.mapping[rea_instrument]
        raw = self.adapter.get_quote(broker_symbol) or {}

        bid = _safe_float(raw.get("bid"))
        ask = _safe_float(raw.get("ask"))
        mid = _safe_float(raw.get("mid"))

        if mid is None and bid is not None and ask is not None:
            mid = (bid + ask) / 2.0

        spread = None
        if bid is not None and ask is not None:
            spread = max(0.0, ask - bid)

        raw_ts = raw.get("timestamp")
        quote_ts = _safe_float(raw_ts)

        # If adapter doesn't provide a timestamp, treat as "now"
        if quote_ts is None:
            quote_ts = ts_now

        quote_age_ms = int(max(0.0, (ts_now - float(quote_ts)) * 1000.0))

        return QuoteSnapshot(
            source=getattr(self.adapter, "name", "unknown"),
            symbol=broker_symbol,
            rea_instrument=rea_instrument,
            bid=bid,
            ask=ask,
            mid=mid,
            spread=spread,
            quote_age_ms=quote_age_ms,
            timestamp=ts_now,
        )


def _safe_float(x) -> Optional[float]:
    try:
        if x is None:
            return None
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).strip().replace(",", "")
        if not s:
            return None
        return float(s)
    except Exception:
        return None


if __name__ == "__main__":
    raise RuntimeError(
        "LiveQuoteRouter is a library module only; it cannot be executed standalone."
    )
