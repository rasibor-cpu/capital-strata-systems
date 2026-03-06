"""
Capital Strata Systems
Portfolio Backtest Engine v4
Trend Filter + Profit Target + Risk Control
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests


COINBASE = "https://api.exchange.coinbase.com"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT = PROJECT_ROOT / "audit_logs" / "backtests"
OUT.mkdir(parents=True, exist_ok=True)


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
            "granularity": granularity,
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


def ma(values, n):

    if len(values) < n:
        return None

    return sum(values[-n:]) / n


def slope(values, n):

    if len(values) < n:
        return 0

    return values[-1] - values[-n]


def backtest_asset(product, capital, days, granularity):

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    candles = fetch(product, granularity, start, end)

    lookback = 20
    ma_len = 50

    trigger = 80
    stop = 70
    take = 80

    closes = []

    cash = capital
    position = None

    trades = []

    for i, c in enumerate(candles):

        closes.append(c.close)

        if i < ma_len:
            continue

        trend = ma(closes, ma_len)
        trend_strength = slope(closes, 10)

        window = candles[i - lookback:i]
        v = vwap(window)

        if v is None:
            continue

        spread = ((c.close - v) / v) * 10000

        if position is None:

            if (
                c.close > trend
                and spread < -trigger
                and trend_strength > 0
            ):

                size = min(cash, capital * 0.1)
                asset = size / c.close

                position = {
                    "entry": c.close,
                    "size": asset,
                    "time": i
                }

                cash -= size

        else:

            entry = position["entry"]

            move = ((c.close - entry) / entry) * 10000

            if move > take or move < -stop or c.close >= v:

                pnl = (c.close - entry) * position["size"]

                cash += position["size"] * c.close

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

        r = backtest_asset(
            asset,
            capital * weight,
            30,
            3600
        )

        results.append(r)

    portfolio_equity = sum(r["final_equity"] for r in results)

    return {
        "assets": results,
        "portfolio_equity": portfolio_equity,
        "portfolio_pnl": round(portfolio_equity - capital, 2)
    }


def main():

    result = run_portfolio()

    print("\nCSS PORTFOLIO BACKTEST v4\n")

    for a in result["assets"]:
        print(a)

    print("\nPortfolio Equity:", result["portfolio_equity"])
    print("Portfolio PnL:", result["portfolio_pnl"])

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    f = OUT / f"portfolio_backtest_v4_{stamp}.json"

    f.write_text(json.dumps(result, indent=2))

    print("\nSaved:", f)


if __name__ == "__main__":
    main()