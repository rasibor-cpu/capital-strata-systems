"""
Capital Strata Systems
Autonomous Trading Engine v37

Improvements
- portfolio risk governor
- opportunity ranking
- max position control
- multi-asset architecture ready

Cycle:
scan → rank → enforce portfolio limits → trade
"""

from __future__ import annotations

import json
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

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
    "UNI-USD",
]

ACCOUNT_EQUITY = 1000
RISK_PER_TRADE = 0.01

MAX_OPEN_POSITIONS = 3

GRANULARITY = 900
LOOKBACK_DAYS = 20
CHUNK = 200

LOOP_INTERVAL = 900

STATE_DIR = Path("backend/state")
LOG_DIR = Path("audit_logs/paper_trades")

STATE_DIR.mkdir(parents=True, exist_ok=True)
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
                "granularity": GRANULARITY,
            },
            timeout=30,
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
            abs(c.low - prev),
        )

        trs.append(tr)

        prev = c.close

    return statistics.mean(trs)


def vwap(candles):

    pv = 0
    vol = 0

    for c in candles:

        typical = (c.high + c.low + c.close) / 3

        pv += typical * c.volume
        vol += c.volume

    if vol == 0:
        return None

    return pv / vol


def trend_score(candles):

    closes = [c.close for c in candles]

    ema20 = ema(closes[-20:], 20)
    ema50 = ema(closes[-50:], 50)

    if ema20 is None or ema50 is None:
        return None

    return (closes[-1] - closes[-20]) / closes[-20]


def reversion_score(candles):

    closes = [c.close for c in candles]

    price = closes[-1]

    v = vwap(candles[-30:])

    if v is None:
        return None

    spread_bps = ((price - v) / v) * 10000

    return -spread_bps


def position_open(asset):

    fname = asset.replace("-", "_")

    path = STATE_DIR / f"pos_{fname}.json"

    if not path.exists():
        return False

    data = json.loads(path.read_text())

    return data.get("status") == "OPEN"


def save_position(asset, trade):

    fname = asset.replace("-", "_")

    path = STATE_DIR / f"pos_{fname}.json"

    trade["status"] = "OPEN"

    path.write_text(json.dumps(trade, indent=2))


def open_position_count():

    count = 0

    for f in STATE_DIR.glob("pos_*.json"):

        data = json.loads(f.read_text())

        if data.get("status") == "OPEN":
            count += 1

    return count


def score_asset(asset):

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=LOOKBACK_DAYS)

    candles = fetch(asset, start, end)

    if len(candles) < 80:
        return None

    trend = trend_score(candles)
    rev = reversion_score(candles)

    if trend is None and rev is None:
        return None

    score = max(
        abs(trend) if trend else 0,
        abs(rev) if rev else 0,
    )

    return {
        "asset": asset,
        "trend": trend,
        "reversion": rev,
        "candles": candles,
        "score": score,
    }


def execute_trade(asset, candles, strategy):

    price = candles[-1].close

    atr_val = atr(candles[-20:])

    stop = price - atr_val * 2

    risk = price - stop

    size = (ACCOUNT_EQUITY * RISK_PER_TRADE) / risk

    trade = {
        "asset": asset,
        "strategy": strategy,
        "entry": price,
        "stop": stop,
        "size": size,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    print("\nTRADE SIGNAL")

    print(trade)

    save_position(asset, trade)

    out = LOG_DIR / f"trade_{asset}_{int(time.time())}.json"

    out.write_text(json.dumps(trade, indent=2))


def run_cycle():

    print("\n==============================")

    print("CSS AUTONOMOUS ENGINE v37")

    print(datetime.now(timezone.utc))

    print("==============================\n")

    open_positions = open_position_count()

    if open_positions >= MAX_OPEN_POSITIONS:

        print("Portfolio limit reached → no new trades")

        return

    scored = []

    for asset in UNIVERSE:

        if position_open(asset):
            continue

        s = score_asset(asset)

        if s:
            scored.append(s)

    scored = sorted(scored, key=lambda x: x["score"], reverse=True)

    available_slots = MAX_OPEN_POSITIONS - open_positions

    selected = scored[:available_slots]

    for s in selected:

        asset = s["asset"]
        candles = s["candles"]

        trend = s["trend"]
        rev = s["reversion"]

        if rev and rev > abs(trend):

            print(asset, "using VWAP reversion")

            execute_trade(asset, candles, "VWAP_REVERSION")

        elif trend:

            print(asset, "using TREND_PULLBACK")

            execute_trade(asset, candles, "TREND_PULLBACK")


def main():

    print("\nCSS AUTONOMOUS ENGINE v37 STARTED\n")

    while True:

        run_cycle()

        print("\nSleeping 15 minutes...\n")

        time.sleep(LOOP_INTERVAL)


if __name__ == "__main__":
    main()