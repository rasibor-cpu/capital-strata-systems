"""
Capital Strata Systems
BTC Volatility Adaptive Backtest v18
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

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT = PROJECT_ROOT / "audit_logs" / "backtests"
OUT.mkdir(parents=True, exist_ok=True)


CONFIG = {
    "test_days": 180,
    "granularity": 900,
    "vol_window": 20,
    "trigger_mult": 1.8,
    "cooldown": 8,
    "position_size": 0.05,
    "take_bps": 120,
    "stop_bps": 80,
    "fee_rate": 0.0006
}


@dataclass
class Candle:
    ts: int
    close: float
    volume: float


def iso(t):
    return t.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch(product, start, end):

    url = f"{COINBASE}/products/{product}/candles"

    candles = []

    step = CONFIG["granularity"] * 200
    cursor = start

    while cursor < end:

        chunk = min(cursor + timedelta(seconds=step), end)

        params = {
            "start": iso(cursor),
            "end": iso(chunk),
            "granularity": CONFIG["granularity"]
        }

        r = requests.get(url, params=params)

        if r.status_code != 200:
            raise RuntimeError(r.text)

        for row in r.json():

            ts, low, high, open_, close, vol = row
            candles.append(Candle(ts, float(close), float(vol)))

        cursor = chunk
        time.sleep(0.15)

    candles = {c.ts: c for c in candles}

    return sorted(candles.values(), key=lambda x: x.ts)


def vwap(data):

    pv = 0
    vol = 0

    for c in data:
        pv += c.close * c.volume
        vol += c.volume

    if vol == 0:
        return None

    return pv / vol


def backtest():

    capital = 1000
    cash = capital
    position = None
    trades = []

    cooldown = 0

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=CONFIG["test_days"])

    candles = fetch("BTC-USD", start, end)

    closes = []

    for i, c in enumerate(candles):

        price = c.close
        closes.append(price)

        if i < 40:
            continue

        if cooldown > 0:
            cooldown -= 1
            continue

        window = candles[i-20:i]
        v = vwap(window)

        if v is None:
            continue

        spread = (price - v) / v

        vol = statistics.stdev(closes[-CONFIG["vol_window"]:])

        trigger = (vol / price) * CONFIG["trigger_mult"]

        if position is None:

            if spread < -trigger:

                size = cash * CONFIG["position_size"]
                asset = size / price

                fee = size * CONFIG["fee_rate"]

                cash -= size + fee

                position = {
                    "entry": price,
                    "size": asset
                }

        else:

            entry = position["entry"]

            move = (price - entry) / entry

            if move > CONFIG["take_bps"]/10000 or move < -CONFIG["stop_bps"]/10000:

                pnl = (price - entry) * position["size"]

                trade_value = position["size"] * price
                fee = trade_value * CONFIG["fee_rate"]

                cash += trade_value + pnl - fee

                trades.append(pnl)

                position = None

                cooldown = CONFIG["cooldown"]

    equity = cash

    if position:
        equity += position["size"] * candles[-1].close

    wins = len([t for t in trades if t > 0])

    return {
        "trades": len(trades),
        "wins": wins,
        "losses": len(trades) - wins,
        "final_equity": round(equity,2),
        "pnl": round(equity - capital,2)
    }


def main():

    result = backtest()

    print("\nCSS VOLATILITY BACKTEST v18\n")
    print(result)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    out = OUT / f"volatility_backtest_v18_{stamp}.json"

    out.write_text(json.dumps(result, indent=2))

    print("\nSaved:", out)


if __name__ == "__main__":
    main()