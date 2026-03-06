"""
Capital Strata Systems (CSS)
BTC Trend Pullback Continuation Backtest v23

Goal:
- Improve v21 (near breakeven) by reducing chop entries and improving exits.

Changes vs v21:
1) Trend strength filter: EMA50 slope must exceed threshold (avoid sideways chop).
2) Intrabar stop simulation: stop triggers on candle LOW (safer, more realistic).
3) Profit management: partial take-profit at +1R, then trail the remainder with ATR.

Long-only, BTC-USD, 15m candles, fees included.
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
    "slope_lookback_bars": 8,      # slope = EMA50(now) - EMA50(N bars ago)
    "min_slope_pct": 0.0012,       # require EMA50 slope >= 0.12% of price
    "atr_window": 20,
    "atr_stop_mult": 2.0,          # initial stop distance
    "trail_atr_mult": 2.5,         # trailing stop distance
    "min_atr_pct": 0.004,          # skip low-vol chop
    "cooldown_bars": 10,
    "position_size": 0.05,
    "fee_rate": 0.0006,
    # Profit-taking:
    "partial_tp_r_multiple": 1.0,  # take partial at +1R
    "partial_sell_frac": 0.50,     # sell 50% at TP1
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
    prev_close = candles[0].close
    for c in candles[1:]:
        tr = max(c.high - c.low, abs(c.high - prev_close), abs(c.low - prev_close))
        trs.append(tr)
        prev_close = c.close
    return statistics.mean(trs) if trs else None


def backtest() -> dict:
    capital = 1000.0
    cash = capital

    # Position state:
    # - entry: float
    # - size_btc: float (remaining)
    # - init_r: float (risk per BTC in USD terms)
    # - stop: float (hard stop)
    # - peak: float (peak close since entry, for trailing)
    # - tp1_done: bool
    position = None

    trades_pnl: List[float] = []

    cooldown = 0
    in_pullback = False

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=CFG["test_days"])
    candles = fetch_candles("BTC-USD", start, end, CFG["granularity"])

    closes: List[float] = []

    warmup = max(CFG["ema_slow"], CFG["atr_window"]) + CFG["slope_lookback_bars"] + 5

    for i, c in enumerate(candles):
        closes.append(c.close)
        price = c.close

        if i < warmup:
            continue

        if cooldown > 0:
            cooldown -= 1

        ema20_now = ema(closes[-CFG["ema_fast"] :], CFG["ema_fast"])
        ema50_now = ema(closes[-CFG["ema_slow"] :], CFG["ema_slow"])

        # EMA50 in the past for slope
        ema50_prev = ema(
            closes[-CFG["ema_slow"] - CFG["slope_lookback_bars"] : -CFG["slope_lookback_bars"]],
            CFG["ema_slow"],
        )

        if ema20_now is None or ema50_now is None or ema50_prev is None:
            continue

        slope = ema50_now - ema50_prev
        slope_ok = (slope / price) >= CFG["min_slope_pct"]

        atr_val = atr(candles[i - CFG["atr_window"] : i + 1])
        if atr_val is None:
            continue

        # Volatility gate
        if (atr_val / price) < CFG["min_atr_pct"]:
            continue

        uptrend = price > ema50_now

        # Pullback detection (must be in strong trend environment)
        if uptrend and slope_ok and price <= ema20_now:
            in_pullback = True

        # ======================
        # ENTRY (after pullback)
        # ======================
        if position is None:
            if cooldown == 0 and uptrend and slope_ok and in_pullback and price > ema20_now:
                size_usd = cash * CFG["position_size"]
                if size_usd <= 0:
                    in_pullback = False
                    continue

                fee_in = size_usd * CFG["fee_rate"]
                cash -= (size_usd + fee_in)

                size_btc = size_usd / price

                # initial stop uses ATR
                stop = price - (CFG["atr_stop_mult"] * atr_val)

                init_r_per_btc = price - stop  # USD risk per BTC

                position = {
                    "entry": price,
                    "size_btc": size_btc,
                    "stop": stop,
                    "peak": price,
                    "tp1_done": False,
                    "init_r_per_btc": init_r_per_btc,
                }

                in_pullback = False
                continue

        # ======================
        # MANAGE / EXIT
        # ======================
        if position is not None:
            # Update peak close for trailing logic
            if price > position["peak"]:
                position["peak"] = price

            # Trailing stop based on peak close
            trail_stop = position["peak"] - (CFG["trail_atr_mult"] * atr_val)

            # Active stop is max of initial stop and trail stop (never loosen)
            active_stop = max(position["stop"], trail_stop)
            position["stop"] = active_stop

            # Profit-taking at +1R (based on initial R per BTC)
            tp1_level = position["entry"] + (CFG["partial_tp_r_multiple"] * position["init_r_per_btc"])

            # TP1 uses intrabar HIGH (more realistic)
            if (not position["tp1_done"]) and (c.high >= tp1_level):
                frac = CFG["partial_sell_frac"]
                sell_btc = position["size_btc"] * frac
                if sell_btc > 0:
                    sell_value = sell_btc * tp1_level
                    fee_out = sell_value * CFG["fee_rate"]

                    pnl = (tp1_level - position["entry"]) * sell_btc - fee_out
                    trades_pnl.append(pnl)

                    cash += sell_value - fee_out
                    position["size_btc"] -= sell_btc
                    position["tp1_done"] = True

            # Stop uses intrabar LOW
            if c.low <= position["stop"]:
                exit_px = position["stop"]
                sell_btc = position["size_btc"]
                sell_value = sell_btc * exit_px
                fee_out = sell_value * CFG["fee_rate"]

                pnl = (exit_px - position["entry"]) * sell_btc - fee_out
                trades_pnl.append(pnl)

                cash += sell_value - fee_out

                position = None
                cooldown = CFG["cooldown_bars"]
                continue

    # final equity
    equity = cash
    if position is not None:
        equity += position["size_btc"] * candles[-1].close

    wins = sum(1 for t in trades_pnl if t > 0)
    losses = sum(1 for t in trades_pnl if t <= 0)

    return {
        "strategy": "trend_pullback_v23",
        "trades": len(trades_pnl),
        "wins": wins,
        "losses": losses,
        "win_rate": round((wins / len(trades_pnl)) * 100, 2) if trades_pnl else 0.0,
        "final_equity": round(equity, 2),
        "pnl": round(equity - capital, 2),
        "params": {
            "ema20": CFG["ema_fast"],
            "ema50": CFG["ema_slow"],
            "min_slope_pct": CFG["min_slope_pct"],
            "atr_stop_mult": CFG["atr_stop_mult"],
            "trail_atr_mult": CFG["trail_atr_mult"],
            "tp1_R": CFG["partial_tp_r_multiple"],
            "tp1_frac": CFG["partial_sell_frac"],
            "cooldown": CFG["cooldown_bars"],
        },
    }


def main() -> None:
    res = backtest()
    print("\nCSS TREND PULLBACK BACKTEST v23\n")
    print(res)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = OUT / f"trend_pullback_backtest_v23_{stamp}.json"
    out.write_text(json.dumps(res, indent=2))
    print("\nSaved:", out)


if __name__ == "__main__":
    main()