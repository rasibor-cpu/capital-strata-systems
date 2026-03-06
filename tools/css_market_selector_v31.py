"""
Capital Strata Systems
Market Selection Engine v32

VWAP Mean Reversion Opportunity Scanner

Improvements over v31:
- volatility sanity filter
- minimum liquidity filter
- clearer scoring logic
- safer market selection

Designed for integration with the CSS trading engine.
"""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import requests


COINBASE = "https://api.exchange.coinbase.com"


SCAN_PRODUCTS = [
    "BTC-USD",
    "ETH-USD",
    "SOL-USD",
    "AVAX-USD",
    "LINK-USD",
    "ATOM-USD",
    "AAVE-USD",
    "MATIC-USD",
    "LTC-USD",
    "UNI-USD",
]


GRANULARITY = 900
LOOKBACK_DAYS = 5
CHUNK_CANDLES = 200


# safety thresholds
MAX_VOLATILITY = 0.05
MIN_VOLUME = 5


@dataclass
class Candle:
    ts: int
    low: float
    high: float
    open: float
    close: float
    volume: float


def iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch(product: str, start: datetime, end: datetime) -> List[Candle]:

    url = f"{COINBASE}/products/{product}/candles"
    candles: List[Candle] = []

    step_seconds = GRANULARITY * CHUNK_CANDLES
    cursor = start

    while cursor < end:

        chunk_end = min(cursor + timedelta(seconds=step_seconds), end)

        r = requests.get(
            url,
            params={
                "start": iso(cursor),
                "end": iso(chunk_end),
                "granularity": GRANULARITY,
            },
            timeout=30,
        )

        if r.status_code != 200:
            return []

        data = r.json()

        for row in data:

            if not isinstance(row, list) or len(row) < 6:
                continue

            ts, low, high, open_, close, vol = row

            candles.append(
                Candle(
                    int(ts),
                    float(low),
                    float(high),
                    float(open_),
                    float(close),
                    float(vol),
                )
            )

        cursor = chunk_end
        time.sleep(0.12)

    uniq = {c.ts: c for c in candles}
    return sorted(uniq.values(), key=lambda x: x.ts)


def compute_vwap(candles: List[Candle]) -> Optional[float]:

    if not candles:
        return None

    pv = 0
    vol = 0

    for c in candles:

        typical = (c.high + c.low + c.close) / 3

        pv += typical * c.volume
        vol += c.volume

    if vol == 0:
        return None

    return pv / vol


def atr(candles: List[Candle]) -> Optional[float]:

    if len(candles) < 2:
        return None

    trs = []
    prev = candles[0].close

    for c in candles[1:]:

        tr = max(
            c.high - c.low,
            abs(c.high - prev),
            abs(c.low - prev),
        )

        trs.append(tr)
        prev = c.close

    if not trs:
        return None

    return statistics.mean(trs)


def opportunity(product: str):

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=LOOKBACK_DAYS)

    candles = fetch(product, start, end)

    if len(candles) < 40:
        return None

    closes = [c.close for c in candles]

    mid = closes[-1]

    vwap = compute_vwap(candles[-30:])
    if vwap is None:
        return None

    spread_bps = ((mid - vwap) / vwap) * 10000

    atr_val = atr(candles[-20:])
    if atr_val is None:
        return None

    volatility = atr_val / mid

    volume = statistics.mean([c.volume for c in candles[-20:]])

    # safety filters
    if volatility > MAX_VOLATILITY:
        return None

    if volume < MIN_VOLUME:
        return None

    # prefer large negative spreads
    score = abs(spread_bps) * volume

    return {
        "product": product,
        "mid": mid,
        "vwap": vwap,
        "spread_bps": spread_bps,
        "volatility": volatility,
        "volume": volume,
        "score": score,
    }


def main():

    print("\nCSS OPPORTUNITY SCANNER v32\n")

    results = []

    for p in SCAN_PRODUCTS:

        try:

            r = opportunity(p)

            if r:

                results.append(r)

                print(
                    f"{p} mid {r['mid']:.2f} "
                    f"vwap {r['vwap']:.2f} "
                    f"spread {r['spread_bps']:.2f} bps"
                )

            else:
                print(f"{p} rejected")

            time.sleep(0.2)

        except Exception as e:
            print(f"{p} error {e}")

    results = sorted(results, key=lambda x: x["score"], reverse=True)

    print("\nTop Opportunities\n")

    for r in results[:5]:

        print(
            f"{r['product']} "
            f"mid {r['mid']:.2f} "
            f"vwap {r['vwap']:.2f} "
            f"spread {r['spread_bps']:.2f} bps"
        )


if __name__ == "__main__":
    main()