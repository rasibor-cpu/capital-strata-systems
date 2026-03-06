"""
Capital Strata Systems (CSS)
BTC Trend Pullback Continuation Backtest v21

Idea:
- Direction filter: EMA(50)
- Pullback zone: price <= EMA(20) (in uptrend)
- Entry trigger: re-cross above EMA(20) after pullback
- Exit: ATR-based stop + trailing stop
- Goal: fewer, higher-quality momentum entries (avoid chasing tops)

Notes:
- Long-only (BTC-USD), 15m candles
- Includes fees
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
    "ema_fast": 20,
    "ema_slow": 50,
    "atr_window": 20,
    "atr_stop_mult": 2.0,        # initial stop = entry - 2*ATR
    "trail_atr_mult": 2.5,       # trailing stop = max(close) - 2.5*ATR
    "min_atr_pct": 0.004,        # avoid dead zones (0.4% ATR/price)
    "cooldown_bars": 8,
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

    # de-dupe by ts, keep last
    uniq = {c.ts: c for c in candles}
    out = sorted(uniq.values(), key=lambda x: x.ts)
    return out


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
    prev_close = candles[0].close
    for c in candles[1:]:
        tr = max(c.high - c.low, abs(c.high - prev_close), abs(c.low - prev_close))
        trs.append(tr)
        prev_close = c.close
    return statistics.mean(trs) if trs else None


def backtest() -> dict:
    capital = 1000.0
    cash = capital
    position = None  # dict(entry, size_btc, stop, trail_peak)
    trades = []
    cooldown = 0

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=CFG["test_days"])
    candles = fetch_candles("BTC-USD", start, end, CFG["granularity"])

    closes: List[float] = []
    in_pullback = False

    for i, c in enumerate(candles):
        price = c.close
        closes.append(price)

        if i < max(CFG["ema_slow"], CFG["atr_window"]) + 5:
            continue

        if cooldown > 0:
            cooldown -= 1

        ema20 = ema(closes[-CFG["ema_fast"] :], CFG["ema_fast"])
        ema50 = ema(closes[-CFG["ema_slow"] :], CFG["ema_slow"])
        if ema20 is None or ema50 is None:
            continue

        atr_val = atr(candles[i - CFG["atr_window"] : i + 1])
        if atr_val is None:
            continue

        # volatility gate
        if (atr_val / price) < CFG["min_atr_pct"]:
            continue

        uptrend = price > ema50

        # Track pullback state: price dips to/below ema20 while in uptrend
        if uptrend and price <= ema20:
            in_pullback = True

        # ENTRY: after pullback, price re-crosses ABOVE ema20 in uptrend + cooldown done
        if position is None:
            if cooldown == 0 and uptrend and in_pullback and price > ema20:
                # enter long
                size_usd = cash * CFG["position_size"]
                if size_usd <= 0:
                    continue

                fee_in = size_usd * CFG["fee_rate"]
                cash -= (size_usd + fee_in)

                size_btc = size_usd / price
                stop = price - (CFG["atr_stop_mult"] * atr_val)
                trail_peak = price

                position = {
                    "entry": price,
                    "size_btc": size_btc,
                    "stop": stop,
                    "trail_peak": trail_peak,
                    "fee_in": fee_in,
                }
                in_pullback = False  # reset after entry
                continue

        # MANAGE / EXIT
        if position is not None:
            # update peak and trailing stop
            if price > position["trail_peak"]:
                position["trail_peak"] = price

            trail_stop = position["trail_peak"] - (CFG["trail_atr_mult"] * atr_val)
            active_stop = max(position["stop"], trail_stop)

            # exit if stop hit (close-based; conservative enough for backtest)
            if price <= active_stop:
                trade_value = position["size_btc"] * price
                fee_out = trade_value * CFG["fee_rate"]

                pnl = (price - position["entry"]) * position["size_btc"] - fee_out - 0.0
                cash += trade_value - fee_out  # value returned minus fee
                trades.append(pnl)

                position = None
                cooldown = CFG["cooldown_bars"]
                continue

    # final equity
    equity = cash
    if position is not None:
        equity += position["size_btc"] * candles[-1].close

    wins = sum(1 for t in trades if t > 0)
    losses = len(trades) - wins

    return {
        "strategy": "trend_pullback_v21",
        "trades": len(trades),
        "wins": wins,
        "losses": losses,
        "win_rate": round((wins / len(trades)) * 100, 2) if trades else 0.0,
        "final_equity": round(equity, 2),
        "pnl": round(equity - capital, 2),
    }


def main() -> None:
    res = backtest()
    print("\nCSS TREND PULLBACK BACKTEST v21\n")
    print(res)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = OUT / f"trend_pullback_backtest_v21_{stamp}.json"
    out.write_text(json.dumps(res, indent=2))
    print("\nSaved:", out)


if __name__ == "__main__":
    main()