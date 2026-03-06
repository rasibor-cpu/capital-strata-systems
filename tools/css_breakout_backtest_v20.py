"""
Capital Strata Systems
BTC Breakout Strategy Backtest v20
Momentum + Volatility Expansion
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
    "ema_period": 50,
    "atr_window": 20,
    "breakout_window": 20,
    "position_size": 0.05,
    "take_profit": 0.02,
    "stop_loss": 0.012,
    "fee_rate": 0.0006
}


@dataclass
class Candle:
    ts: int
    close: float
    high: float
    low: float
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

            candles.append(
                Candle(ts, float(close), float(high), float(low), float(vol))
            )

        cursor = chunk
        time.sleep(0.15)

    candles = {c.ts: c for c in candles}

    return sorted(candles.values(), key=lambda x: x.ts)


def ema(values, period):

    k = 2 / (period + 1)
    e = values[0]

    for v in values:
        e = v * k + e * (1 - k)

    return e


def atr(candles):

    trs = []

    for c in candles:
        trs.append(c.high - c.low)

    return statistics.mean(trs)


def backtest():

    capital = 1000
    cash = capital
    position = None
    trades = []

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=CONFIG["test_days"])

    candles = fetch("BTC-USD", start, end)

    closes = []

    for i, c in enumerate(candles):

        price = c.close
        closes.append(price)

        if i < 60:
            continue

        ema_val = ema(closes[-CONFIG["ema_period"]:], CONFIG["ema_period"])

        atr_val = atr(candles[i-CONFIG["atr_window"]:i])

        highs = [x.high for x in candles[i-CONFIG["breakout_window"]:i]]

        breakout = max(highs)

        if position is None:

            if price > ema_val and price > breakout:

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

            if move > CONFIG["take_profit"] or move < -CONFIG["stop_loss"]:

                pnl = (price - entry) * position["size"]

                trade_value = position["size"] * price

                fee = trade_value * CONFIG["fee_rate"]

                cash += trade_value + pnl - fee

                trades.append(pnl)

                position = None

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

    print("\nCSS BREAKOUT BACKTEST v20\n")

    print(result)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    out = OUT / f"breakout_backtest_v20_{stamp}.json"

    out.write_text(json.dumps(result, indent=2))

    print("\nSaved:", out)


if __name__ == "__main__":
    main()