"""
Capital Strata Systems
Portfolio Backtest Engine v9
VWAP Pullback Strategy + ATR Volatility Filter
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


MARKET_TYPE = "crypto"


CONFIG = {
    "rsi_period": 9,
    "rsi_entry": 40,
    "trigger_mult": 0.9,
    "test_days": 180
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


def atr(values):

    if len(values) < 20:
        return None

    return statistics.stdev(values[-20:])


def backtest_asset(product, capital, granularity):

    end = datetime.now(timezone.utc)

    start = end - timedelta(days=CONFIG["test_days"])

    candles = fetch(product, granularity, start, end)

    closes = []

    lookback = 20

    stop = 70
    take = 80

    cash = capital

    position = None

    trades = []

    diag = {
        "bars": 0,
        "blocked_rsi": 0,
        "blocked_trigger": 0,
        "blocked_vol": 0,
        "entries": 0
    }

    for i, c in enumerate(candles):

        diag["bars"] += 1

        price = c.close

        closes.append(price)

        if i < 50:
            continue

        trend_strength = slope(closes, 10)

        if trend_strength < -0.05:

            diag["blocked_vol"] += 1

            continue

        window = candles[i - lookback:i]

        v = vwap(window)

        if v is None:
            continue

        spread = ((price - v) / v) * 10000

        r = rsi(closes, CONFIG["rsi_period"])

        if r is None or r > CONFIG["rsi_entry"]:

            diag["blocked_rsi"] += 1

            continue

        vol_bps = volatility_bps(closes, price)

        if vol_bps is None:
            continue

        trigger = vol_bps * CONFIG["trigger_mult"]

        if spread > -trigger:

            diag["blocked_trigger"] += 1

            continue

        if position is None:

            size = min(cash, capital * 0.1)

            asset = size / price

            position = {
                "entry": price,
                "size": asset
            }

            cash -= size

            diag["entries"] += 1

        else:

            entry = position["entry"]

            move = ((price - entry) / entry) * 10000

            if move > take or move < -stop or price >= v:

                pnl = (price - entry) * position["size"]

                cash += position["size"] * price

                trades.append(pnl)

                position = None

    equity = cash

    if position:
        equity += position["size"] * candles[-1].close

    wins = len([t for t in trades if t > 0])

    return {
        "product": product,
        "trades": len(trades),
        "wins": wins,
        "losses": len(trades) - wins,
        "pnl": round(equity - capital, 2),
        "final_equity": round(equity, 2),
        "diagnostics": diag
    }


def run_portfolio():

    capital = 1000

    alloc = {
        "BTC-USD": 0.5,
        "ETH-USD": 0.3,
        "SOL-USD": 0.2
    }

    results = []

    for asset, weight in alloc.items():

        r = backtest_asset(asset, capital * weight, 3600)

        results.append(r)

    portfolio_equity = sum(r["final_equity"] for r in results)

    return {
        "assets": results,
        "portfolio_equity": portfolio_equity,
        "portfolio_pnl": round(portfolio_equity - capital, 2)
    }


def main():

    result = run_portfolio()

    print("\nCSS PORTFOLIO BACKTEST v9\n")

    for a in result["assets"]:
        print(a)

    print("\nPortfolio Equity:", result["portfolio_equity"])
    print("Portfolio PnL:", result["portfolio_pnl"])

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    f = OUT / f"portfolio_backtest_v9_{stamp}.json"

    f.write_text(json.dumps(result, indent=2))

    print("\nSaved:", f)


if __name__ == "__main__":
    main()