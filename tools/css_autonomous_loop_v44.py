"""
Capital Strata Systems
Autonomous Trading Engine v44

New in v44
----------
• Trend-aware profit holding
• EMA trailing stop exit
• ATR dynamic protection
• backward-compatible position files
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
MAX_OPEN_POSITIONS = 3

MIN_ASSET_PRICE = 0.50
MAX_CAPITAL_PER_TRADE = 0.35
MAX_TOKEN_SIZE = 500

TOP_MARKETS = 15
MAX_DISCOVERED_TO_RANK = 80

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


# ------------------------------------------------
# INDICATORS
# ------------------------------------------------

def ema(values, period):

    k = 2 / (period + 1)

    ema_val = values[0]

    for v in values[1:]:

        ema_val = v * k + ema_val * (1 - k)

    return ema_val


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

    return pv / vol


# ------------------------------------------------
# MARKET DISCOVERY
# ------------------------------------------------

def discover_markets():

    r = requests.get(f"{COINBASE}/products", timeout=15)

    markets = []

    for p in r.json():

        if p.get("quote_currency") != "USD":
            continue

        if p.get("status") != "online":
            continue

        markets.append(p["id"])

    return sorted(markets)[:MAX_DISCOVERED_TO_RANK]


# ------------------------------------------------
# LIQUIDITY RANKING
# ------------------------------------------------

def rank_liquidity(markets):

    liquidity = []

    for m in markets:

        try:

            r = requests.get(f"{COINBASE}/products/{m}/stats", timeout=6)

            vol = float(r.json()["volume"])

            liquidity.append((m, vol))

        except:
            continue

    liquidity.sort(key=lambda x: x[1], reverse=True)

    return [x[0] for x in liquidity[:TOP_MARKETS]]


# ------------------------------------------------
# DATA FETCH
# ------------------------------------------------

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
            timeout=15,
        )

        for row in r.json():

            ts, low, high, open_, close, vol = row

            candles.append(Candle(ts, low, high, open_, close, vol))

        cursor = chunk_end

    uniq = {c.ts: c for c in candles}

    return sorted(uniq.values(), key=lambda x: x.ts)


def get_price(asset):

    try:

        r = requests.get(f"{COINBASE}/products/{asset}/ticker", timeout=6)

        return float(r.json()["price"])

    except:

        return None


# ------------------------------------------------
# POSITION MANAGEMENT
# ------------------------------------------------

def position_files():

    return list(STATE_DIR.glob("pos_*.json"))


def save_position(asset, trade):

    fname = asset.replace("-", "_")

    path = STATE_DIR / f"pos_{fname}.json"

    trade["status"] = "OPEN"

    path.write_text(json.dumps(trade, indent=2))


def close_position(file_path, price):

    data = json.loads(file_path.read_text())

    pnl = (price - data["entry"]) * data["size"]

    data["exit_price"] = price
    data["exit_time"] = datetime.now(timezone.utc).isoformat()
    data["pnl"] = pnl
    data["status"] = "CLOSED"

    file_path.write_text(json.dumps(data, indent=2))

    print("POSITION CLOSED", data["asset"], pnl)


def monitor_positions():

    for f in position_files():

        data = json.loads(f.read_text())

        if data.get("status") != "OPEN":
            continue

        price = get_price(data["asset"])

        if price is None:
            continue

        # fetch recent candles
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=3)

        candles = fetch(data["asset"], start, end)

        closes = [c.close for c in candles]

        ema10 = ema(closes[-10:], 10)

        atr_val = atr(candles[-20:])

        trail = ema10 - atr_val

        # ratchet stop upward
        data["stop"] = max(data["stop"], trail)

        if price <= data["stop"]:

            close_position(f, price)

        else:

            f.write_text(json.dumps(data, indent=2))


# ------------------------------------------------
# SCORING
# ------------------------------------------------

def score_asset(asset):

    price = get_price(asset)

    if price is None or price < MIN_ASSET_PRICE:
        return None

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=LOOKBACK_DAYS)

    candles = fetch(asset, start, end)

    if len(candles) < 80:
        return None

    closes = [c.close for c in candles]

    v = vwap(candles[-30:])
    atr_val = atr(candles[-20:])

    spread = abs(price - v) / v
    momentum = abs(price - closes[-20]) / closes[-20]
    volatility = atr_val / price

    score = spread + momentum + volatility

    return {"asset": asset, "candles": candles, "score": score}


# ------------------------------------------------
# TRADE EXECUTION
# ------------------------------------------------

def execute_trade(asset, candles, weight):

    price = candles[-1].close

    atr_val = atr(candles[-20:])

    stop = price - atr_val * 2

    capital = ACCOUNT_EQUITY * weight
    capital = min(capital, ACCOUNT_EQUITY * MAX_CAPITAL_PER_TRADE)

    size = capital / price
    size = min(size, MAX_TOKEN_SIZE)

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


# ------------------------------------------------
# ENGINE LOOP
# ------------------------------------------------

def run_cycle():

    print("\n==============================")
    print("CSS AUTONOMOUS ENGINE v44")
    print(datetime.now(timezone.utc))
    print("==============================\n")

    monitor_positions()

    if len(position_files()) >= MAX_OPEN_POSITIONS:

        print("Portfolio limit reached")

        return

    markets = discover_markets()

    liquid = rank_liquidity(markets)

    scored = []

    for asset in liquid:

        s = score_asset(asset)

        if s:
            scored.append(s)

    scored.sort(key=lambda x: x["score"], reverse=True)

    top = scored[:MAX_OPEN_POSITIONS]

    total_score = sum(x["score"] for x in top)

    for s in top:

        weight = s["score"] / total_score

        execute_trade(s["asset"], s["candles"], weight)


def main():

    print("\nCSS AUTONOMOUS ENGINE v44 STARTED\n")

    while True:

        run_cycle()

        print("\nSleeping 15 minutes...\n")

        time.sleep(LOOP_INTERVAL)


if __name__ == "__main__":
    main()