"""
Capital Strata Systems
Market Selection Engine v30 (Fixed)

Scans Coinbase markets and ranks assets by:
- EMA slope
- momentum
- volatility

Fixes:
- chunked candle fetching
- does not discard negative/zero scores
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
LOOKBACK_DAYS = 30
CHUNK_CANDLES = 200


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


def ema(values: List[float], period: int) -> Optional[float]:
    if len(values) < period:
        return None

    k = 2 / (period + 1)
    e = values[0]

    for v in values:
        e = v * k + e * (1 - k)

    return e


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

    return statistics.mean(trs) if trs else None


def trend_score(product: str) -> Optional[float]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=LOOKBACK_DAYS)

    candles = fetch(product, start, end)

    if len(candles) < 80:
        return None

    closes = [c.close for c in candles]

    ema20 = ema(closes[-20:], 20)
    ema50 = ema(closes[-50:], 50)
    ema50_prev = ema(closes[-70:-20], 50)

    if ema20 is None or ema50 is None or ema50_prev is None:
        return None

    atr_val = atr(candles[-20:])
    if atr_val is None:
        return None

    slope = (ema50 - ema50_prev) / closes[-1]
    momentum = (closes[-1] - closes[-20]) / closes[-20]
    volatility = atr_val / closes[-1]

    score = slope + momentum + volatility
    return score


def main() -> None:
    print("\nCSS MARKET SELECTION ENGINE v30\n")

    scores = []

    for p in SCAN_PRODUCTS:
        try:
            s = trend_score(p)

            if s is not None:
                scores.append((p, s))
                print(f"{p} score: {s:.6f}")
            else:
                print(f"{p} score: unavailable")

            time.sleep(0.2)

        except Exception as e:
            print(f"{p} error: {e}")

    scores = sorted(scores, key=lambda x: x[1], reverse=True)

    print("\nTop Trending Assets\n")

    for p, s in scores[:5]:
        print(f"{p} score: {s:.6f}")


if __name__ == "__main__":
    main()