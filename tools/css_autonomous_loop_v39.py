"""
Capital Strata Systems
Autonomous Trading Engine v39

New Features
-------------
• Automatic Coinbase market discovery
• Filters for USD spot pairs
• Liquidity filtering
• Integrated with portfolio governor
• Exit manager retained
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


# -------------------------------
# MARKET DISCOVERY
# -------------------------------

def discover_markets():

    print("Discovering Coinbase markets...")

    r = requests.get(f"{COINBASE}/products", timeout=30)

    if r.status_code != 200:
        return []

    markets = []

    for p in r.json():

        if p["quote_currency"] != "USD":
            continue

        if p["status"] != "online":
            continue

        markets.append(p["id"])

    print("Markets discovered:", len(markets))

    return markets


# -------------------------------
# MARKET DATA
# -------------------------------

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


def get_price(asset):

    r = requests.get(
        f"{COINBASE}/products/{asset}/ticker",
        timeout=10,
    )

    if r.status_code != 200:
        return None

    return float(r.json()["price"])


# -------------------------------
# INDICATORS
# -------------------------------

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


# -------------------------------
# POSITION MANAGEMENT
# -------------------------------

def position_files():

    return list(STATE_DIR.glob("pos_*.json"))


def open_position_count():

    count = 0

    for f in position_files():

        data = json.loads(f.read_text())

        if data["status"] == "OPEN":
            count += 1

    return count


def save_position(asset, trade):

    fname = asset.replace("-", "_")

    path = STATE_DIR / f"pos_{fname}.json"

    trade["status"] = "OPEN"

    path.write_text(json.dumps(trade, indent=2))


def close_position(file_path, price):

    data = json.loads(file_path.read_text())

    entry = data["entry"]
    size = data["size"]

    pnl = (price - entry) * size

    data["exit_price"] = price
    data["exit_time"] = datetime.now(timezone.utc).isoformat()
    data["pnl"] = pnl
    data["status"] = "CLOSED"

    file_path.write_text(json.dumps(data, indent=2))

    log = LOG_DIR / f"closed_{file_path.name}"

    log.write_text(json.dumps(data, indent=2))

    print("POSITION CLOSED", data)


def monitor_positions():

    for f in position_files():

        data = json.loads(f.read_text())

        if data["status"] != "OPEN":
            continue

        asset = data["asset"]

        price = get_price(asset)

        if price is None:
            continue

        stop = data["stop"]

        if price <= stop:

            print(asset, "STOP LOSS HIT")

            close_position(f, price)


# -------------------------------
# OPPORTUNITY SCORING
# -------------------------------

def score_asset(asset):

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=LOOKBACK_DAYS)

    candles = fetch(asset, start, end)

    if len(candles) < 80:
        return None

    closes = [c.close for c in candles]

    price = closes[-1]

    v = vwap(candles[-30:])

    if v is None:
        return None

    spread = abs((price - v) / v)

    volume = sum(c.volume for c in candles[-20:])

    if volume < 100:
        return None

    return {
        "asset": asset,
        "candles": candles,
        "score": spread,
    }


# -------------------------------
# TRADE EXECUTION
# -------------------------------

def execute_trade(asset, candles):

    price = candles[-1].close

    atr_val = atr(candles[-20:])

    stop = price - atr_val * 2

    risk = price - stop

    size = (ACCOUNT_EQUITY * RISK_PER_TRADE) / risk

    trade = {
        "asset": asset,
        "strategy": "VWAP_REVERSION",
        "entry": price,
        "stop": stop,
        "size": size,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    print("TRADE SIGNAL", trade)

    save_position(asset, trade)

    out = LOG_DIR / f"trade_{asset}_{int(time.time())}.json"

    out.write_text(json.dumps(trade, indent=2))


# -------------------------------
# ENGINE CYCLE
# -------------------------------

def run_cycle():

    print("\n==============================")
    print("CSS AUTONOMOUS ENGINE v39")
    print(datetime.now(timezone.utc))
    print("==============================\n")

    monitor_positions()

    open_positions = open_position_count()

    if open_positions >= MAX_OPEN_POSITIONS:

        print("Portfolio limit reached")

        return

    markets = discover_markets()

    scored = []

    for asset in markets:

        fname = asset.replace("-", "_")

        if (STATE_DIR / f"pos_{fname}.json").exists():
            continue

        s = score_asset(asset)

        if s:
            scored.append(s)

    scored = sorted(scored, key=lambda x: x["score"], reverse=True)

    slots = MAX_OPEN_POSITIONS - open_positions

    for s in scored[:slots]:

        execute_trade(s["asset"], s["candles"])


def main():

    print("\nCSS AUTONOMOUS ENGINE v39 STARTED\n")

    while True:

        run_cycle()

        print("\nSleeping 15 minutes...\n")

        time.sleep(LOOP_INTERVAL)


if __name__ == "__main__":
    main()