"""
REA Capital Trading Engine
TwelveData Quote Adapter (READ-ONLY)

Branch: live-adapters
Purpose:
- Fetch live FX quotes from TwelveData
- Conform to QuoteAdapter protocol
- No execution, no orders, no account state

Required outputs (dict):
- bid (optional)
- ask (optional)
- mid (optional)
- timestamp (epoch seconds)
"""

from __future__ import annotations

from typing import Dict, Optional
import time

# NOTE:
# This adapter expects you already have a TwelveData client or HTTP helper.
# We keep it minimal and defensive.


class TwelveDataAdapter:
    name = "twelvedata"

    def __init__(self, client):
        """
        client: an object with a `get_quote(symbol: str) -> dict` method
        Expected client output (flexible):
          - bid / ask OR close / price
          - timestamp (epoch or ISO8601)
        """
        self.client = client

    def get_quote(self, symbol: str) -> Dict:
        """
        Returns a normalized dict with:
          - bid
          - ask
          - mid
          - timestamp (epoch seconds)
        """
        raw = self.client.get_quote(symbol) or {}

        bid = _safe_float(raw.get("bid"))
        ask = _safe_float(raw.get("ask"))

        mid = _safe_float(
            raw.get("mid")
            or raw.get("price")
            or raw.get("close")
        )

        if mid is None and bid is not None and ask is not None:
            mid = (bid + ask) / 2.0

        ts = _parse_ts(raw.get("timestamp"))

        return {
            "bid": bid,
            "ask": ask,
            "mid": mid,
            "timestamp": ts,
        }


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


def _parse_ts(x) -> float:
    """
    Returns epoch seconds.
    Falls back to now() if missing or invalid.
    """
    try:
        if x is None:
            return time.time()
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).strip()
        if s.isdigit():
            return float(s)
    except Exception:
        pass
    return time.time()


if __name__ == "__main__":
    raise RuntimeError(
        "TwelveDataAdapter is a library module only; it cannot be executed standalone."
    )
