"""
FX Daily Rates – REA Capital Trading Engine
-------------------------------------------

Purpose:
- Provide a stable, engine-wide FX conversion function used by risk/credit limits.
- Keep the API contract expected by credit_limits.py: get_fx_rate(...)

Phase-1 design:
- Same currency conversion returns 1.0
- Cross-currency conversion is fail-closed by default:
    - If no rate is available, raise RuntimeError so callers can BLOCK safely.
- Rates are loaded from a local JSON cache file (optional), configurable via env var.

Expected JSON format (example):
{
  "as_of": "2026-02-04",
  "rates": {
    "USDUSD": 1.0,
    "USDEUR": 0.92,
    "EURUSD": 1.087
  },
  "source": "manual|provider_name"
}
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, Tuple


DEFAULT_RATES_FILE = os.path.join(os.path.dirname(__file__), "data", "fx_daily_rates.json")


@dataclass(frozen=True)
class FxRateSnapshot:
    as_of: str
    source: str
    rates: Dict[str, float]


def _pair_key(base_ccy: str, quote_ccy: str) -> str:
    return f"{base_ccy.strip().upper()}{quote_ccy.strip().upper()}"


def _load_snapshot(path: str) -> Optional[FxRateSnapshot]:
    if not path:
        return None
    if not os.path.exists(path):
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        as_of = str(raw.get("as_of") or raw.get("date") or "")
        source = str(raw.get("source") or "unknown")
        rates_raw = raw.get("rates") or {}

        rates: Dict[str, float] = {}
        if isinstance(rates_raw, dict):
            for k, v in rates_raw.items():
                try:
                    rates[str(k).strip().upper()] = float(v)
                except Exception:
                    continue

        if not as_of:
            # best-effort fallback
            as_of = datetime.utcnow().date().isoformat()

        return FxRateSnapshot(as_of=as_of, source=source, rates=rates)
    except Exception:
        return None


def get_fx_rate(
    base_ccy: str,
    quote_ccy: str,
    *,
    fail_closed: bool = True,
    rates_file: Optional[str] = None,
) -> float:
    """
    Return FX rate for converting base_ccy -> quote_ccy.

    - If base_ccy == quote_ccy: returns 1.0
    - Otherwise tries to load from JSON cache file.
    - If not found and fail_closed=True: raises RuntimeError (caller should BLOCK).
    - If not found and fail_closed=False: returns 1.0 (NOT recommended for live).

    This function exists to satisfy imports from credit_limits.py.
    """
    b = (base_ccy or "").strip().upper()
    q = (quote_ccy or "").strip().upper()

    if not b or not q:
        if fail_closed:
            raise RuntimeError("FX rate lookup failed: missing currency code.")
        return 1.0

    if b == q:
        return 1.0

    path = rates_file or os.getenv("REA_FX_RATES_FILE") or DEFAULT_RATES_FILE
    snap = _load_snapshot(path)

    pair = _pair_key(b, q)
    if snap and pair in snap.rates:
        return float(snap.rates[pair])

    # Optional: try inverse if present
    inv = _pair_key(q, b)
    if snap and inv in snap.rates:
        r = float(snap.rates[inv])
        if r != 0.0:
            return 1.0 / r

    if fail_closed:
        raise RuntimeError(f"FX rate lookup failed: no rate for {pair} (file={path}).")
    return 1.0
