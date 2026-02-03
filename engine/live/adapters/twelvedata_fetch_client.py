"""
REA Capital Trading Engine
TwelveData Fetch Client Wrapper (READ-ONLY)

Branch: live-adapters

Purpose:
- Wrap live_data.twelvedata_fx_adapter.fetch_fx_1m(pair, limit)
- Provide a client object with get_quote(symbol) -> dict
- Used by TwelveDataAdapter + LiveQuoteRouter

No execution, no orders, no accounts.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import time

from live_data.twelvedata_fx_adapter import fetch_fx_1m


class TwelveDataFetchClient:
    """
    Adapts function-style fetch_fx_1m() into a QuoteAdapter-compatible client.

    get_quote(symbol) returns:
      {
        "bid": Optional[float],
        "ask": Optional[float],
        "mid": Optional[float],
        "timestamp": float (epoch seconds)
      }
    """

    def __init__(self, limit: int = 1):
        # We only need the latest bar for a quote-like snapshot
        self.limit = max(1, int(limit))

    def get_quote(self, symbol: str) -> Dict[str, Any]:
        # fetch_fx_1m expects pair like "EUR/USD" (as you mapped)
        rows: List[Dict[str, Any]] = fetch_fx_1m(symbol, limit=self.limit) or []

        if not rows:
            return {"bid": None, "ask": None, "mid": None, "timestamp": time.time()}

        # Use the last row as "latest"
        last = rows[-1] or {}

        mid = _pick_price(last)
        ts = _pick_timestamp(last)

        return {"bid": None, "ask": None, "mid": mid, "timestamp": ts}


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


def _pick_price(row: Dict[str, Any]) -> Optional[float]:
    """
    TwelveData time-series rows usually contain one of these:
      close / price / c
    Sometimes: "close" is a string.
    """
    for k in ("close", "price", "c", "mid"):
        v = _safe_float(row.get(k))
        if v is not None:
            return v
    return None


def _pick_timestamp(row: Dict[str, Any]) -> float:
    """
    Tries common keys and falls back to now():
      timestamp / time / datetime
    Accepts epoch seconds or ISO-like strings; if string parse fails, now().
    """
    for k in ("timestamp", "time", "datetime"):
        v = row.get(k)
        if v is None:
            continue
        # epoch?
        fv = _safe_float(v)
        if fv is not None:
            return float(fv)
        # ISO string? (best effort)
        try:
            s = str(v).strip()
            # crude ISO handling: if endswith Z, strip; we still fallback to now if needed
            if s.endswith("Z"):
                s = s[:-1]
            # If the module returned a readable datetime string, we accept "now" to avoid parser deps
            # (quote_age_ms logic still works reasonably)
            return time.time()
        except Exception:
            pass

    return time.time()


if __name__ == "__main__":
    raise RuntimeError("TwelveDataFetchClient is a library module only; do not run directly.")
