"""
Alpaca Data Adapter (Crypto Snapshot)
-------------------------------------

Uses Alpaca data endpoint to fetch latest crypto quote.

Env vars expected:
- APCA_API_KEY_ID
- APCA_API_SECRET_KEY
Optional:
- ALPACA_DATA_URL : defaults to https://data.alpaca.markets
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Dict, Any

import requests


DEFAULT_DATA_URL = "https://data.alpaca.markets"


def _require_env(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return v


def _alpaca_headers() -> Dict[str, str]:
    return {
        "APCA-API-KEY-ID": _require_env("APCA_API_KEY_ID"),
        "APCA-API-SECRET-KEY": _require_env("APCA_API_SECRET_KEY"),
        "Accept": "application/json",
    }


def fetch_alpaca_crypto_snapshot(provider_symbol: str) -> Dict[str, Any]:
    """
    provider_symbol example: "BTC/USD"
    """
    base = os.environ.get("ALPACA_DATA_URL", DEFAULT_DATA_URL).strip().rstrip("/")
    url = f"{base}/v1beta3/crypto/us/latest/quotes"
    params = {"symbols": provider_symbol}

    r = requests.get(url, headers=_alpaca_headers(), params=params, timeout=20)

    if r.status_code != 200:
        body = r.text[:800]
        raise RuntimeError(
            f"Alpaca crypto quote failed: HTTP {r.status_code}. "
            f"URL={url} symbols={provider_symbol}. "
            f"Body(first800)={body}"
        )

    data = r.json()
    quotes = (data.get("quotes") or {})
    q = quotes.get(provider_symbol)
    if not q:
        raise RuntimeError(f"No quote returned for {provider_symbol}")

    return {
        "source": "alpaca",
        "symbol": provider_symbol,
        "ap": q.get("ap"),
        "bp": q.get("bp"),
        "as": q.get("as"),
        "bs": q.get("bs"),
        "t": q.get("t"),
        "raw": q,
        "ts_utc": datetime.now(timezone.utc).isoformat(),
    }
