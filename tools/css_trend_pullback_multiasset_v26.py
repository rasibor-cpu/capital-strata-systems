"""
Capital Strata Systems (CSS)
Trend Pullback Multi-Asset Backtest v26

Runs the v25 Trend Pullback engine across multiple crypto products:
- BTC-USD
- ETH-USD
- SOL-USD

Outputs:
- per-asset summary (trades/wins/losses/win_rate/final_equity/pnl)
- portfolio aggregate (sum of pnl, avg pnl, total trades)
- saves JSON results in audit_logs/backtests/

NOTE: Backtest only (research). No live trading.
"""

from __future__ import annotations

import json
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import requests

COINBASE = "https://api.exchange.coinbase.com"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT = PROJECT_ROOT / "audit_logs" / "backtests"
OUT.mkdir(parents=True, exist_ok=True)

CFG = {
    "test_days": 180,
    "granularity": 900,  # 15m
    "ema_fast": 20,
    "ema_slow": 50,
    "slope_lookback": 8,
    "min_slope_pct": 0.0013,
    "atr_window": 20,
    "atr_stop_mult": 2.0,
    "trail_atr_mult": 3.5,
    "min_atr_pct": 0.004,
    "cooldown": 10,
    "position_size": 0.05,
    "fee_rate": 0.0006,
    "tp1_r": 2.0,
    "tp1_frac": 0.5,
}

PRODUCTS = ["BTC-USD", "ETH-USD", "SOL-USD"]


@dataclass
class Candle:
    ts: int
    low: float
    high: float
    open: float
    close: float
    volume: float


def _iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch(product: str, start: datetime, end: datetime, gran: int) -> List[Candle]:
    url = f"{COINBASE}/products/{product}/candles"
    candles: List[Candle] = []

    step = gran * 200
    cursor = start

    while cursor < end:
        chunk = min(cursor + timedelta(seconds=step), end)
        params = {"start": _iso(cursor), "end": _iso(chunk), "granularity": gran}

        r = requests.get(url, params=params)
        if r.status_code != 200:
            raise RuntimeError(f"{product} Coinbase request failed {r.status_code}: {r.text[:200]}")

        for row in r.json():
            ts, low, high, open_, close, vol = row
            candles.append(Candle(int(ts), float(low), float(high), float(open_), float(close), float(vol)))

        cursor = chunk
        time.sleep(0.12)

    uniq = {c.ts: c for c in candles}
    return sorted(uniq.values(), key=lambda x: x.ts)


def ema(values: List[float], period: int) -> Optional[float]:
    if len(values) < period:
        return None
    k = 2 / (period + 1)
    e = values[0]
    for v in values:
        e = v * k + e * (1 - k)
    return e


def atr(candles: List[Candle]) -> Optional[float]:
    if len(candles) < 2:
        return None
    trs = []
    prev = candles[0].close
    for c in candles[1:]:
        tr = max(c.high - c.low, abs(c.high - prev), abs(c.low - prev))
        trs.append(tr)
        prev = c.close
    return statistics.mean(trs) if trs else None


def run_engine(product: str) -> Dict[str, float]:
    capital = 1000.0
    cash = capital
    position = None
    cooldown = 0
    trades: List[float] = []
    in_pullback = False

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=CFG["test_days"])
    candles = fetch(product, start, end, CFG["granularity"])

    closes: List[float] = []
    warm = max(CFG["ema_slow"], CFG["atr_window"]) + CFG["slope_lookback"] + 5

    for i, c in enumerate(candles):
        closes.append(c.close)
        price = c.close

        if i < warm:
            continue

        if cooldown > 0:
            cooldown -= 1

        ema20 = ema(closes[-CFG["ema_fast"] :], CFG["ema_fast"])
        ema50 = ema(closes[-CFG["ema_slow"] :], CFG["ema_slow"])
        ema50_prev = ema(
            closes[-CFG["ema_slow"] - CFG["slope_lookback"] : -CFG["slope_lookback"]],
            CFG["ema_slow"],
        )

        if ema20 is None or ema50 is None or ema50_prev is None:
            continue

        slope = (ema50 - ema50_prev) / price
        if slope < CFG["min_slope_pct"]:
            continue

        atr_val = atr(candles[i - CFG["atr_window"] : i + 1])
        if atr_val is None:
            continue

        if (atr_val / price) < CFG["min_atr_pct"]:
            continue

        uptrend = price > ema50

        # pullback detection
        if uptrend and price <= ema20:
            in_pullback = True

        # entry
        if position is None and cooldown == 0 and in_pullback and price > ema20:
            size_usd = cash * CFG["position_size"]
            if size_usd <= 0:
                in_pullback = False
                continue

            fee_in = size_usd * CFG["fee_rate"]
            cash -= (size_usd + fee_in)

            size = size_usd / price
            stop = price - (CFG["atr_stop_mult"] * atr_val)
            r = price - stop

            position = {"entry": price, "size": size, "stop": stop, "peak": price, "r": r, "tp1_done": False}
            in_pullback = False

        # manage
        if position is not None:
            if price > position["peak"]:
                position["peak"] = price

            trail = position["peak"] - (CFG["trail_atr_mult"] * atr_val)
            if trail > position["stop"]:
                position["stop"] = trail

            tp1 = position["entry"] + (CFG["tp1_r"] * position["r"])

            if (not position["tp1_done"]) and c.high >= tp1:
                sell = position["size"] * CFG["tp1_frac"]
                val = sell * tp1
                fee_out = val * CFG["fee_rate"]
                pnl = (tp1 - position["entry"]) * sell - fee_out
                trades.append(pnl)
                cash += val - fee_out
                position["size"] -= sell
                position["tp1_done"] = True

            if c.low <= position["stop"]:
                exitp = position["stop"]
                sell = position["size"]
                val = sell * exitp
                fee_out = val * CFG["fee_rate"]
                pnl = (exitp - position["entry"]) * sell - fee_out
                trades.append(pnl)
                cash += val - fee_out
                position = None
                cooldown = CFG["cooldown"]

    equity = cash
    if position is not None:
        equity += position["size"] * candles[-1].close

    wins = sum(1 for t in trades if t > 0)
    losses = sum(1 for t in trades if t <= 0)

    return {
        "product": product,
        "trades": int(len(trades)),
        "wins": int(wins),
        "losses": int(losses),
        "win_rate": round((wins / len(trades)) * 100, 2) if trades else 0.0,
        "final_equity": round(equity, 2),
        "pnl": round(equity - capital, 2),
    }


def main() -> None:
    print("\nCSS TREND PULLBACK MULTI-ASSET BACKTEST v26\n")

    results = []
    total_trades = 0
    total_pnl = 0.0

    for p in PRODUCTS:
        r = run_engine(p)
        results.append(r)
        total_trades += int(r["trades"])
        total_pnl += float(r["pnl"])
        print(r)

    summary = {
        "strategy": "trend_pullback_multiasset_v26",
        "params": CFG,
        "results": results,
        "portfolio_total_trades": total_trades,
        "portfolio_total_pnl": round(total_pnl, 2),
        "portfolio_avg_pnl_per_asset": round((total_pnl / len(PRODUCTS)), 2),
    }

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = OUT / f"trend_pullback_multiasset_v26_{stamp}.json"
    out.write_text(json.dumps(summary, indent=2))
    print("\nSaved:", out)


if __name__ == "__main__":
    main()