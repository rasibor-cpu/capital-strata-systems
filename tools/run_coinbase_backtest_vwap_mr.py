"""
CSS Backtest Engine v2
BTC Stabilization Version
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

import requests

COINBASE_API = "https://api.exchange.coinbase.com"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "audit_logs" / "backtests"
OUT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Candle:
    ts: int
    close: float
    volume: float


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_candles(product, granularity, start, end):

    url = f"{COINBASE_API}/products/{product}/candles"

    rows = []
    step = granularity * 200
    cursor = start

    while cursor < end:

        chunk_end = min(cursor + timedelta(seconds=step), end)

        params = {
            "start": iso(cursor),
            "end": iso(chunk_end),
            "granularity": granularity,
        }

        r = requests.get(url, params=params)

        if r.status_code != 200:
            raise RuntimeError(r.text)

        for row in r.json():

            ts, low, high, open_, close, vol = row

            rows.append(Candle(ts, float(close), float(vol)))

        cursor = chunk_end

        time.sleep(0.15)

    rows = {c.ts: c for c in rows}

    return sorted(rows.values(), key=lambda x: x.ts)


def moving_average(data, n):

    if len(data) < n:
        return None

    return sum(data[-n:]) / n


def vwap(data):

    pv = 0
    vol = 0

    for c in data:
        pv += c.close * c.volume
        vol += c.volume

    return pv / vol if vol > 0 else None


def run_backtest(product, granularity, days, capital):

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    candles = fetch_candles(product, granularity, start, end)

    lookback = 20
    ma_period = 50

    trigger_bps = 80
    stop_loss_bps = 70

    max_hold = 12

    cash = capital
    position = None

    trades = []

    closes = []

    for i, c in enumerate(candles):

        closes.append(c.close)

        if i < ma_period:
            continue

        ma50 = moving_average(closes, ma_period)

        window = candles[i - lookback:i]

        v = vwap(window)

        if v is None:
            continue

        spread = ((c.close - v) / v) * 10000

        if position is None:

            if c.close > ma50 and spread < -trigger_bps:

                size = min(20, cash)

                asset = size / c.close

                position = {
                    "entry": c.close,
                    "asset": asset,
                    "time": i
                }

                cash -= size

        else:

            hold = i - position["time"]

            entry = position["entry"]

            move = ((c.close - entry) / entry) * 10000

            if c.close >= v or move < -stop_loss_bps or hold >= max_hold:

                pnl = (c.close - entry) * position["asset"]

                cash += position["asset"] * c.close

                trades.append(pnl)

                position = None

    equity = cash

    if position:
        equity += position["asset"] * candles[-1].close

    wins = sum(1 for x in trades if x > 0)

    losses = sum(1 for x in trades if x <= 0)

    gross_profit = sum(x for x in trades if x > 0)

    gross_loss = abs(sum(x for x in trades if x < 0))

    profit_factor = gross_profit / gross_loss if gross_loss else 0

    return {
        "trades": len(trades),
        "wins": wins,
        "losses": losses,
        "win_rate": wins / len(trades) if trades else 0,
        "profit_factor": profit_factor,
        "final_equity": round(equity, 2),
        "pnl": round(equity - capital, 2)
    }


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument("--product", default="BTC-USD")
    parser.add_argument("--granularity", type=int, default=900)
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--capital", type=float, default=200)

    args = parser.parse_args()

    result = run_backtest(
        args.product,
        args.granularity,
        args.days,
        args.capital
    )

    print("\nCSS BACKTEST ENGINE v2\n")

    for k, v in result.items():
        print(k, ":", v)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    f = OUT_DIR / f"backtest_v2_{stamp}.json"

    f.write_text(json.dumps(result, indent=2))

    print("\nSaved:", f)


if __name__ == "__main__":
    main()