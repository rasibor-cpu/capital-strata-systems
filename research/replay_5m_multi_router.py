"""
tools/replay_5m_multi_router.py

Multi-Strategy Regime Router (5m)

Routing logic:
- TRENDING_UP      -> Breakout (long only)
- TRENDING_DOWN    -> Breakout (short only)
- MEAN_REVERTING   -> Mean reversion
- NEUTRAL          -> Flat

Exit rule:
- Exit on hold completion
- OR exit early if regime opposes trade direction
"""

from __future__ import annotations
import argparse
from typing import Dict, Any, Optional

import pandas as pd

from engine.regime.regime_classifier import (
    classify_regime,
    TRENDING_UP,
    TRENDING_DOWN,
    MEAN_REVERTING,
)

# ------------------------------------------------------------
# Indicators
# ------------------------------------------------------------

def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()

def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)

    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return tr.rolling(period, min_periods=period).mean()

# ------------------------------------------------------------
# Normalization
# ------------------------------------------------------------

def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    cols = {c.lower().strip(): c for c in df.columns}

    def pick(*names):
        for n in names:
            if n in cols:
                return cols[n]
        return None

    t = pick("timestamp", "time", "datetime", "date", "ts", "ts_utc")
    o = pick("open", "o")
    h = pick("high", "h")
    l = pick("low", "l")
    c = pick("close", "c")

    if None in [t, o, h, l, c]:
        raise ValueError("CSV must contain time + OHLC")

    out = df.rename(columns={t: "ts", o: "open", h: "high", l: "low", c: "close"})
    out["ts"] = pd.to_datetime(out["ts"])
    out = out.set_index("ts").sort_index()

    return out

def _to_5m(df: pd.DataFrame) -> pd.DataFrame:
    return df.resample("5min").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last"
    }).dropna()

# ------------------------------------------------------------
# Signals
# ------------------------------------------------------------

def breakout_signal(bar, prev, atr, cut):
    up = prev["high"] + cut * atr
    down = prev["low"] - cut * atr

    if bar["close"] >= up:
        return "BUY"
    if bar["close"] <= down:
        return "SELL"
    return "FLAT"

def mean_reversion_signal(bar, mid, atr, k):
    upper = mid + k * atr
    lower = mid - k * atr

    if bar["close"] > upper:
        return "SELL"
    if bar["close"] < lower:
        return "BUY"
    return "FLAT"

# ------------------------------------------------------------
# Router Replay
# ------------------------------------------------------------

def run_router(df5, regime, atr, mid, hold, scale, breakout_cut, mr_k):

    equity = 100000
    peak = equity
    max_dd = 0

    trades = 0
    wins = 0

    position: Optional[Dict[str, Any]] = None

    for i in range(1, len(df5)):

        bar = df5.iloc[i]
        prev = df5.iloc[i - 1]
        reg = regime.iloc[i]
        atr_val = atr.iloc[i]
        mid_val = mid.iloc[i]

        # --- EXIT LOGIC ---
        if position:
            position["bars"] += 1

            # Regime opposition exit (Choice C)
            if (
                (position["dir"] == "LONG" and reg == TRENDING_DOWN)
                or
                (position["dir"] == "SHORT" and reg == TRENDING_UP)
            ):
                exit_price = bar["close"]
                entry = position["entry"]
                pnl = (exit_price - entry) * scale if position["dir"] == "LONG" else (entry - exit_price) * scale
                equity += pnl
                trades += 1
                if pnl > 0:
                    wins += 1
                position = None
                continue

            # Hold exit
            if position["bars"] >= hold:
                exit_price = bar["close"]
                entry = position["entry"]
                pnl = (exit_price - entry) * scale if position["dir"] == "LONG" else (entry - exit_price) * scale
                equity += pnl
                trades += 1
                if pnl > 0:
                    wins += 1
                position = None

        # --- ENTRY LOGIC ---
        if not position and not pd.isna(atr_val):

            if reg == TRENDING_UP:
                sig = breakout_signal(bar, prev, atr_val, breakout_cut)
                if sig == "BUY":
                    position = {"dir": "LONG", "entry": bar["close"], "bars": 0}

            elif reg == TRENDING_DOWN:
                sig = breakout_signal(bar, prev, atr_val, breakout_cut)
                if sig == "SELL":
                    position = {"dir": "SHORT", "entry": bar["close"], "bars": 0}

            elif reg == MEAN_REVERTING:
                sig = mean_reversion_signal(bar, mid_val, atr_val, mr_k)
                if sig == "BUY":
                    position = {"dir": "LONG", "entry": bar["close"], "bars": 0}
                elif sig == "SELL":
                    position = {"dir": "SHORT", "entry": bar["close"], "bars": 0}

        # --- DD tracking ---
        peak = max(peak, equity)
        dd = (peak - equity) / peak
        max_dd = max(max_dd, dd)

    win_rate = (wins / trades * 100) if trades else 0

    return {
        "trades": trades,
        "win_rate": win_rate,
        "exp": equity - 100000,
        "max_dd": max_dd * 100,
        "eq_end": equity
    }

# ------------------------------------------------------------
# CLI
# ------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv")
    parser.add_argument("--hold", type=int, required=True)
    parser.add_argument("--scale", type=float, default=100)
    parser.add_argument("--breakout_cut", type=float, default=0.2)
    parser.add_argument("--mr_k", type=float, default=0.25)

    args = parser.parse_args()

    df = pd.read_csv(args.csv)
    df = _normalize(df)
    df5 = _to_5m(df)

    atr = _atr(df5)
    mid = _ema(df5["close"], 20)
    regime = classify_regime(df5)

    res = run_router(df5, regime, atr, mid, args.hold, args.scale, args.breakout_cut, args.mr_k)

    print("\n=== MULTI-STRATEGY ROUTER RESULT ===")
    for k, v in res.items():
        print(f"{k:10}: {v}")

if __name__ == "__main__":
    main()