"""
TwelveData FX Adapter (FREE FEED)
--------------------------------
Purpose:
- Pull FX price data from TwelveData free tier
- Normalize into REA canonical tick format
- NO execution, NO trading, data-only feed

Notes:
- Free tier: limited calls/minute
- Best for 1m–15m bars (scalable later)
"""

import os
import requests
from datetime import datetime, timezone

BASE_URL = "https://api.twelvedata.com/time_series"


def fetch_fx_bars(
    pair: str,
    interval: str = "1min",
    outputsize: int = 100,
):
    api_key = os.getenv("TWELVEDATA_API_KEY")
    if not api_key:
        raise RuntimeError("TWELVEDATA_API_KEY not set")

    symbol = pair.replace("/", "")

    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": api_key,
        "format": "JSON",
    }

    r = requests.get(BASE_URL, params=params, timeout=15)
    r.raise_for_status()
    payload = r.json()

    if "values" not in payload:
        raise RuntimeError(f"Bad response: {payload}")

    bars = []
    for row in reversed(payload["values"]):
        ts = datetime.fromisoformat(row["datetime"]).replace(tzinfo=timezone.utc)
        bars.append({
            "ts_utc": ts.isoformat(),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": None,
        })

    return bars


if __name__ == "__main__":
    # smoke test
    data = fetch_fx_bars("EUR/USD", interval="1min", outputsize=5)
    for b in data:
        print(b)
