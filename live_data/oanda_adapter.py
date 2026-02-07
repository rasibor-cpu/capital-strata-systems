"""
OANDA Practice Adapter (Live Snapshot)
--------------------------------------

Fetches a pricing snapshot from OANDA (practice) using REST v3.

Env vars expected:
- OANDA_TOKEN        : your API token
- OANDA_ACCOUNT_ID   : your account id (e.g. 101-001-xxxxxxx-001)
Optional:
- OANDA_API_URL      : defaults to https://api-fxpractice.oanda.com
"""

from __future__ import annotations

import os
import json
from datetime import datetime, timezone
from typing import Dict, Any

import requests


DEFAULT_OANDA_API_URL = "https://api-fxpractice.oanda.com"


def _require_env(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return v


def _oanda_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def fetch_oanda_snapshot(provider_symbol: str) -> Dict[str, Any]:
    """
    provider_symbol example: "EUR_USD"
    Returns a compact, engine-friendly snapshot dict.
    """
    token = _require_env("OANDA_TOKEN")
    account_id = _require_env("OANDA_ACCOUNT_ID")
    base = os.environ.get("OANDA_API_URL", DEFAULT_OANDA_API_URL).strip().rstrip("/")

    url = f"{base}/v3/accounts/{account_id}/pricing"
    params = {"instruments": provider_symbol}

    r = requests.get(url, headers=_oanda_headers(token), params=params, timeout=20)

    # Fail-closed with useful debug
    if r.status_code != 200:
        body = r.text[:800]
        raise RuntimeError(
            f"OANDA pricing call failed: HTTP {r.status_code}. "
            f"URL={url} instruments={provider_symbol}. "
            f"Body(first800)={body}"
        )

    data = r.json()

    prices = data.get("prices") or []
    if not prices:
        raise RuntimeError(f"OANDA returned no prices for instruments={provider_symbol}")

    p0 = prices[0]

    def _first_price(side: str) -> float | None:
        arr = p0.get(side) or []
        if not arr:
            return None
        try:
            return float(arr[0].get("price"))
        except Exception:
            return None

    bid = _first_price("bids")
    ask = _first_price("asks")

    snap = {
        "source": "oanda",
        "instrument": p0.get("instrument", provider_symbol),
        "time": p0.get("time"),
        "bid": bid,
        "ask": ask,
        "status": p0.get("status"),
        "tradeable": p0.get("tradeable"),
        "raw": p0,  # keep raw for audit/debug
        "ts_utc": datetime.now(timezone.utc).isoformat(),
    }
    return snap
