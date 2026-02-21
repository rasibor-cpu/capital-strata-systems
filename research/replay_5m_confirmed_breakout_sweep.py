"""
ATR-Scaled 5M Breakout Sweep
Now Regime-Gated (Institutional Routing)

Rules:
- LONG breakout allowed only in TRENDING_UP
- SHORT breakout allowed only in TRENDING_DOWN
"""

from __future__ import annotations
import argparse
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple

import pandas as pd

from engine.regime.regime_classifier import (
    classify_regime,
    TRENDING_UP,
    TRENDING_DOWN,
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
# Data normalization
# ------------------------------------------------------------

def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols = {c.lower().strip(): c for c in df.columns}

    def pick(*names: str):
        for n in names:
            if n in cols:
                return cols[n]
        return None

    tcol = pick("timestamp", "time", "datetime", "date", "ts", "ts_utc")
    o = pick("open", "o")
    h = pick("high", "h")
    l = pick("low", "l")
    c = pick("close", "c")

    if None in [tcol, o, h, l, c]:
        raise ValueError("CSV must contain time + OHLC columns")

    df = df.rename(columns={tcol: "ts", o: "open", h: "high", l: "low", c: "close"})
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.set_index("ts").sort_index()

    return df

def _to_5m(df: pd.DataFrame) -> pd.DataFrame:
    return df.resample("5min").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last"
    }).dropna()


# ------------------------------------------------------------
# Breakout logic (ATR scaled)
# ------------------------------------------------------------

def breakout_signal(bar, prev_bar, atr, cut):
    prev_high = prev_bar["high"]
    prev_low = prev_bar["low"]
    close = bar["close"]

    up = prev_high + cut * atr
    down = prev_low - cut * atr

    if close >= up:
        return "BUY"
    if close <= down:
        return "SELL"
    return "FLAT"


# ------------------------------------------------------------
# Replay
# ------------------------------------------------------------

def run_replay(df5, cut, hold, scale, regime, atr):

    equity = 100000
    peak = equity
    max_dd = 0
    trades = 0
    wins = 0

    position = None

    for i in range(1, len(df5)):

        bar = df5.iloc[i]
        prev = df5.iloc[i - 1]
        reg = regime.iloc[i]
        atr_val = atr.iloc[i]

        # exit
        if position:
            position["bars"] += 1
            if position["bars"] >= hold:
                exit_price = bar["close"]
                entry = position["entry"]
                direction = position["dir"]

                pnl = (exit_price - entry) * scale if direction == "LONG" else (entry - exit_price) * scale
                equity += pnl
                trades += 1
                if pnl > 0:
                    wins += 1
                position = None

        # entry
        if not position and not pd.isna(atr_val):

            sig = breakout_signal(bar, prev, atr_val, cut)

            # Regime gating
            if sig == "BUY" and reg == TRENDING_UP:
                position = {"dir": "LONG", "entry": bar["close"], "bars": 0}

            elif sig == "SELL" and reg == TRENDING_DOWN:
                position = {"dir": "SHORT", "entry": bar["close"], "bars": 0}

        # DD tracking
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
    parser.add_argument("--min", type=float, required=True)
    parser.add_argument("--max", type=float, required=True)
    parser.add_argument("--step", type=float, required=True)
    parser.add_argument("--hold", type=int, required=True)
    parser.add_argument("--scale", type=float, default=100)

    args = parser.parse_args()

    df = pd.read_csv(args.csv)
    df = _normalize_columns(df)
    df5 = _to_5m(df)

    atr = _atr(df5)
    regime = classify_regime(df5)

    print("\n=== REGIME-GATED ATR BREAKOUT ===")
    print("cut   trades  win%   exp     maxDD%  eq_end")

    cut = args.min
    while cut <= args.max:
        res = run_replay(df5, cut, args.hold, args.scale, regime, atr)

        print(f"{cut:4.2f}  {res['trades']:6}  {res['win_rate']:5.1f}  {res['exp']:7.2f}  {res['max_dd']:7.3f}  {res['eq_end']:9.2f}")

        cut += args.step


if __name__ == "__main__":
    main()