"""
Capital Strata Systems
Autonomous Trader v31b

Fully automated pipeline:
scan → rank → select → strategy
"""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import requests

COINBASE = "https://api.exchange.coinbase.com"

UNIVERSE = [
    "BTC-USD",
    "ETH-USD",
    "SOL-USD",
    "AVAX-USD",
    "LINK-USD",
    "ATOM-USD",
    "AAVE-USD",
    "MATIC-USD",
    "LTC-USD",
    "UNI-USD"
]

TOP_ASSETS = 3

GRANULARITY = 900
LOOKBACK_DAYS = 30
CHUNK = 200


@dataclass
class Candle:
    ts: int
    low: float
    high: float
    open: float
    close: float
    volume: float


def iso(t):
    return t.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch(product, start, end):

    url = f"{COINBASE}/products/{product}/candles"

    candles = []

    step = GRANULARITY * CHUNK
    cursor = start

    while cursor < end:

        chunk_end = min(cursor + timedelta(seconds=step), end)

        r = requests.get(
            url,
            params={
                "start": iso(cursor),
                "end": iso(chunk_end),
                "granularity": GRANULARITY
            },
            timeout=30
        )

        if r.status_code != 200:
            return []

        for row in r.json():
            ts, low, high, open_, close, vol = row
            candles.append(Candle(ts, low, high, open_, close, vol))

        cursor = chunk_end

        time.sleep(0.12)

    candles = sorted(candles, key=lambda x: x.ts)

    return candles


def ema(values, period):

    if len(values) < period:
        return None

    k = 2 / (period + 1)
    e = values[0]

    for v in values:
        e = v * k + e * (1 - k)

    return e


def atr(candles):

    trs = []

    prev = candles[0].close

    for c in candles[1:]:

        tr = max(
            c.high - c.low,
            abs(c.high - prev),
            abs(c.low - prev)
        )

        trs.append(tr)

        prev = c.close

    return statistics.mean(trs)


def score_asset(asset):

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=LOOKBACK_DAYS)

    candles = fetch(asset, start, end)

    if len(candles) < 80:
        return None

    closes = [c.close for c in candles]

    ema20 = ema(closes[-20:], 20)
    ema50 = ema(closes[-50:], 50)

    ema50_prev = ema(closes[-70:-20], 50)

    if ema20 is None or ema50 is None or ema50_prev is None:
        return None

    atr_val = atr(candles[-20:])

    slope = (ema50 - ema50_prev) / closes[-1]
    momentum = (closes[-1] - closes[-20]) / closes[-20]
    volatility = atr_val / closes[-1]

    score = slope + momentum + volatility

    return score


def select_assets():

    scores = []

    print("\nScanning Market\n")

    for asset in UNIVERSE:

        try:

            s = score_asset(asset)

            if s is not None:

                print(asset, "score:", round(s, 6))

                scores.append((asset, s))

            else:

                print(asset, "score unavailable")

        except Exception as e:

            print(asset, "error")

        time.sleep(0.25)

    scores = sorted(scores, key=lambda x: x[1], reverse=True)

    print("\nTop Assets Selected\n")

    selected = [x[0] for x in scores[:TOP_ASSETS]]

    for s in selected:
        print(s)

    return selected


def run_strategy(asset):

    print("Running trading engine on", asset)


def main():

    print("\nCSS AUTONOMOUS TRADER v31b\n")

    assets = select_assets()

    print("\nExecuting Strategy\n")

    for a in assets:
        run_strategy(a)


if __name__ == "__main__":
    main()