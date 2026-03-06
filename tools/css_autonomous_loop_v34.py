"""
Capital Strata Systems
Autonomous Trading Loop v34

Continuous engine:
scan → select → evaluate → paper trade → repeat every 15 minutes
"""

from __future__ import annotations

import json
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

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

ACCOUNT_EQUITY = 1000
RISK_PER_TRADE = 0.01

GRANULARITY = 900
LOOKBACK_DAYS = 30
CHUNK = 200

LOOP_INTERVAL = 900   # 15 minutes

LOG_DIR = Path("audit_logs/paper_trades")
LOG_DIR.mkdir(parents=True, exist_ok=True)


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

        time.sleep(0.1)

    return sorted(candles, key=lambda x: x.ts)


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

    return slope + momentum + volatility


def select_assets():

    scores = []

    print("\nScanning Market\n")

    for asset in UNIVERSE:

        s = score_asset(asset)

        if s is not None:

            print(asset, "score:", round(s, 6))

            scores.append((asset, s))

        else:

            print(asset, "score unavailable")

        time.sleep(0.2)

    scores = sorted(scores, key=lambda x: x[1], reverse=True)

    print("\nTop Assets Selected\n")

    selected = [x[0] for x in scores[:TOP_ASSETS]]

    for s in selected:
        print(s)

    return selected


def execute_trade(asset):

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=LOOKBACK_DAYS)

    candles = fetch(asset, start, end)

    if len(candles) < 60:
        return

    closes = [c.close for c in candles]

    ema20 = ema(closes[-20:], 20)
    ema50 = ema(closes[-50:], 50)

    price = closes[-1]

    if ema20 > ema50 and price < ema20:

        atr_val = atr(candles[-20:])

        stop = price - atr_val * 2
        risk = price - stop

        position_size = (ACCOUNT_EQUITY * RISK_PER_TRADE) / risk

        trade = {
            "asset": asset,
            "entry": price,
            "stop": stop,
            "size": position_size,
            "timestamp": datetime.utcnow().isoformat()
        }

        print("\nTRADE SIGNAL")
        print(trade)

        out = LOG_DIR / f"trade_{asset}_{int(time.time())}.json"

        out.write_text(json.dumps(trade, indent=2))

    else:

        print(asset, "no entry signal")


def run_cycle():

    print("\n==============================")
    print("CSS AUTONOMOUS CYCLE")
    print(datetime.utcnow())
    print("==============================\n")

    assets = select_assets()

    print("\nEvaluating Trades\n")

    for asset in assets:

        execute_trade(asset)


def main():

    print("\nCSS AUTONOMOUS LOOP v34 STARTED\n")

    while True:

        run_cycle()

        print("\nSleeping 15 minutes...\n")

        time.sleep(LOOP_INTERVAL)


if __name__ == "__main__":
    main()