"""
Capital Strata Systems
BTC Walk-Forward Backtest v16
Institutional robustness test
"""

from __future__ import annotations
import json
import statistics
import time
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from pathlib import Path
import requests


COINBASE = "https://api.exchange.coinbase.com"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT = PROJECT_ROOT / "audit_logs" / "backtests"
OUT.mkdir(parents=True, exist_ok=True)


CONFIG = {
    "train_days": 90,
    "test_days": 30,
    "cycles": 6,
    "granularity": 900,
    "position_size": 0.05,
    "take_bps": 100,
    "stop_bps": 70,
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


def backtest_window(candles):

    capital = 1000
    cash = capital
    position = None
    trades = []

    closes = []

    for i, c in enumerate(candles):

        price = c.close
        closes.append(price)

        if i < 30:
            continue

        window = candles[i-20:i]
        v = vwap(window)

        if v is None:
            continue

        spread = (price - v) / v

        if position is None:

            if spread < -0.004:

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

    equity = cash

    if position:
        equity += position["size"] * candles[-1].close

    return equity - capital


def run():

    end = datetime.now(timezone.utc)

    results = []

    for i in range(CONFIG["cycles"]):

        test_end = end - timedelta(days=i*CONFIG["test_days"])
        test_start = test_end - timedelta(days=CONFIG["test_days"])

        candles = fetch("BTC-USD", test_start, test_end)

        pnl = backtest_window(candles)

        results.append(pnl)

        print(f"Cycle {i+1} PnL:", round(pnl,2))

    avg = statistics.mean(results)

    print("\nWalk-Forward Average:", round(avg,2))

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    out = OUT / f"walkforward_v16_{stamp}.json"

    out.write_text(json.dumps(results, indent=2))

    print("\nSaved:", out)


if __name__ == "__main__":
    run()