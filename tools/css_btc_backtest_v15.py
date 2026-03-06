"""
Capital Strata Systems
BTC Backtest Engine v15
BTC-only strategy isolation
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
    "rsi_period": 9,
    "rsi_entry": 42,
    "trigger_mult": 1.2,
    "test_days": 180,
    "take_bps": 100,
    "stop_bps": 70,
    "position_size": 0.05,
    "fee_rate": 0.0006,
    "cooldown_bars": 5,
    "min_atr_pct": 0.006
}


@dataclass
class Candle:
    ts: int
    close: float
    volume: float


def iso(t):
    return t.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch(product, granularity, start, end):

    url = f"{COINBASE}/products/{product}/candles"

    candles = []

    step = granularity * 200
    cursor = start

    while cursor < end:

        chunk = min(cursor + timedelta(seconds=step), end)

        params = {
            "start": iso(cursor),
            "end": iso(chunk),
            "granularity": granularity
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


def slope(values, n):

    if len(values) < n:
        return 0

    return values[-1] - values[-n]


def rsi(values, period):

    if len(values) < period + 1:
        return None

    gains = []
    losses = []

    for i in range(-period, 0):

        change = values[i] - values[i - 1]

        if change > 0:
            gains.append(change)
        else:
            losses.append(abs(change))

    avg_gain = sum(gains) / period if gains else 0
    avg_loss = sum(losses) / period if losses else 0

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss

    return 100 - (100 / (1 + rs))


def volatility_bps(values, price):

    if len(values) < 20:
        return None

    sd = statistics.stdev(values[-20:])

    return (sd / price) * 10000


def atr_pct(values, price):

    if len(values) < 20:
        return 0

    return statistics.stdev(values[-20:]) / price


def backtest():

    capital = 1000

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=CONFIG["test_days"])

    candles = fetch("BTC-USD", 900, start, end)

    closes = []

    cash = capital
    position = None
    trades = []

    cooldown = 0

    for i, c in enumerate(candles):

        price = c.close
        closes.append(price)

        if i < 50:
            continue

        if cooldown > 0:
            cooldown -= 1
            continue

        atr = atr_pct(closes, price)

        if atr < CONFIG["min_atr_pct"]:
            continue

        trend = slope(closes, 10)

        window = candles[i-20:i]

        v = vwap(window)

        if v is None:
            continue

        spread = ((price - v) / v) * 10000

        r = rsi(closes, CONFIG["rsi_period"])

        vol = volatility_bps(closes, price)

        if vol is None:
            continue

        trigger = vol * CONFIG["trigger_mult"]

        long_signal = (
            trend > -0.05
            and (r is not None and r < CONFIG["rsi_entry"] or spread < -trigger)
        )

        short_signal = (
            trend < 0.05
            and spread > trigger
        )

        if position is None:

            if long_signal or short_signal:

                size = cash * CONFIG["position_size"]

                asset = size / price

                direction = 1 if long_signal else -1

                entry_fee = size * CONFIG["fee_rate"]

                cash -= size + entry_fee

                position = {
                    "entry": price,
                    "size": asset,
                    "dir": direction
                }

        else:

            entry = position["entry"]
            direction = position["dir"]

            move = ((price - entry) / entry) * 10000 * direction

            if move > CONFIG["take_bps"] or move < -CONFIG["stop_bps"]:

                pnl = (price - entry) * position["size"] * direction

                trade_value = position["size"] * price

                exit_fee = trade_value * CONFIG["fee_rate"]

                cash += trade_value + pnl - exit_fee

                trades.append(pnl - exit_fee)

                position = None

                cooldown = CONFIG["cooldown_bars"]

    equity = cash

    if position:
        equity += position["size"] * candles[-1].close

    wins = len([t for t in trades if t > 0])

    return {
        "trades": len(trades),
        "wins": wins,
        "losses": len(trades) - wins,
        "win_rate": round((wins/len(trades))*100,2) if trades else 0,
        "final_equity": round(equity,2),
        "pnl": round(equity - capital,2)
    }


def main():

    result = backtest()

    print("\nCSS BTC BACKTEST v15\n")

    print(result)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    f = OUT / f"btc_backtest_v15_{stamp}.json"

    f.write_text(json.dumps(result, indent=2))

    print("\nSaved:", f)


if __name__ == "__main__":
    main()