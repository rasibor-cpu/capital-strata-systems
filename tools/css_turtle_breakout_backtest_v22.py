"""
Capital Strata Systems (CSS)
BTC Turtle-Style Breakout Backtest v22 (Donchian)

Idea:
- Entry: break above N-bar Donchian high (classic turtle)
- Exit: break below M-bar Donchian low OR ATR stop
- Long-only (BTC-USD), 15m candles
- Includes fees

This is a canonical trend-following template.
"""

from __future__ import annotations

import json
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

import requests

COINBASE = "https://api.exchange.coinbase.com"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT = PROJECT_ROOT / "audit_logs" / "backtests"
OUT.mkdir(parents=True, exist_ok=True)

CFG = {
    "test_days": 180,
    "granularity": 900,  # 15m
    "entry_breakout": 20,  # Donchian high lookback
    "exit_breakout": 10,   # Donchian low lookback
    "atr_window": 20,
    "atr_stop_mult": 2.0,
    "cooldown_bars": 6,
    "position_size": 0.05,
    "fee_rate": 0.0006,
}


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


def fetch_candles(product: str, start: datetime, end: datetime, granularity: int) -> List[Candle]:
    url = f"{COINBASE}/products/{product}/candles"
    candles: List[Candle] = []

    step = granularity * 200
    cursor = start
    while cursor < end:
        chunk = min(cursor + timedelta(seconds=step), end)
        params = {"start": _iso(cursor), "end": _iso(chunk), "granularity": granularity}
        r = requests.get(url, params=params)
        if r.status_code != 200:
            raise RuntimeError(f"Coinbase request failed {r.status_code}: {r.text[:200]}")
        for row in r.json():
            ts, low, high, open_, close, vol = row
            candles.append(Candle(int(ts), float(low), float(high), float(open_), float(close), float(vol)))
        cursor = chunk
        time.sleep(0.12)

    uniq = {c.ts: c for c in candles}
    out = sorted(uniq.values(), key=lambda x: x.ts)
    return out


def atr(candles: List[Candle]) -> Optional[float]:
    if len(candles) < 2:
        return None
    trs = []
    prev_close = candles[0].close
    for c in candles[1:]:
        tr = max(c.high - c.low, abs(c.high - prev_close), abs(c.low - prev_close))
        trs.append(tr)
        prev_close = c.close
    return statistics.mean(trs) if trs else None


def backtest() -> dict:
    capital = 1000.0
    cash = capital
    position = None  # dict(entry, size_btc, stop)
    trades = []
    cooldown = 0

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=CFG["test_days"])
    candles = fetch_candles("BTC-USD", start, end, CFG["granularity"])

    need = max(CFG["entry_breakout"], CFG["exit_breakout"], CFG["atr_window"]) + 2

    for i in range(len(candles)):
        c = candles[i]
        price = c.close

        if i < need:
            continue

        if cooldown > 0:
            cooldown -= 1

        atr_val = atr(candles[i - CFG["atr_window"] : i + 1])
        if atr_val is None:
            continue

        highs = [x.high for x in candles[i - CFG["entry_breakout"] : i]]
        lows = [x.low for x in candles[i - CFG["exit_breakout"] : i]]

        donchian_high = max(highs)
        donchian_low = min(lows)

        if position is None:
            if cooldown == 0 and price > donchian_high:
                size_usd = cash * CFG["position_size"]
                fee_in = size_usd * CFG["fee_rate"]
                cash -= (size_usd + fee_in)

                size_btc = size_usd / price
                stop = price - (CFG["atr_stop_mult"] * atr_val)

                position = {"entry": price, "size_btc": size_btc, "stop": stop, "fee_in": fee_in}
        else:
            # update ATR stop (trail stop up as price rises)
            new_stop = price - (CFG["atr_stop_mult"] * atr_val)
            position["stop"] = max(position["stop"], new_stop)

            exit_signal = (price < donchian_low) or (price <= position["stop"])

            if exit_signal:
                trade_value = position["size_btc"] * price
                fee_out = trade_value * CFG["fee_rate"]
                pnl = (price - position["entry"]) * position["size_btc"] - fee_out

                cash += trade_value - fee_out
                trades.append(pnl)

                position = None
                cooldown = CFG["cooldown_bars"]

    equity = cash
    if position is not None:
        equity += position["size_btc"] * candles[-1].close

    wins = sum(1 for t in trades if t > 0)
    losses = len(trades) - wins

    return {
        "strategy": "turtle_breakout_v22",
        "trades": len(trades),
        "wins": wins,
        "losses": losses,
        "win_rate": round((wins / len(trades)) * 100, 2) if trades else 0.0,
        "final_equity": round(equity, 2),
        "pnl": round(equity - capital, 2),
    }


def main() -> None:
    res = backtest()
    print("\nCSS TURTLE BREAKOUT BACKTEST v22\n")
    print(res)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = OUT / f"turtle_breakout_backtest_v22_{stamp}.json"
    out.write_text(json.dumps(res, indent=2))
    print("\nSaved:", out)


if __name__ == "__main__":
    main()