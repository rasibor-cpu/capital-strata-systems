"""
tools/replay_5m_mean_reversion_sweep.py

Mean-Reversion Sweep (5m, Regime-Gated)

Trades ONLY when regime == MEAN_REVERTING.

Signal idea (institutional, simple):
- Compute EMA(mid) and ATR
- If close > EMA + k*ATR => SHORT (fade extension)
- If close < EMA - k*ATR => LONG  (fade extension)
Exit: fixed hold bars (like breakout tool)

Sweep k over a range.

Usage:
  python -m tools.replay_5m_mean_reversion_sweep sample_spy_1m_long.csv --min 0.25 --max 1.25 --step 0.25 --hold 3 --scale 100
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Optional, Dict, Any, List

import pandas as pd

from engine.regime.regime_classifier import classify_regime, MEAN_REVERTING


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


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
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
        raise ValueError("CSV must contain time + OHLC columns (ts_utc/o/h/l/c supported).")

    out = df.rename(columns={tcol: "ts", o: "open", h: "high", l: "low", c: "close"}).copy()
    out["ts"] = pd.to_datetime(out["ts"], errors="coerce")
    out = out.dropna(subset=["ts"]).sort_values("ts").set_index("ts")
    return out


def _to_5m(df_1m: pd.DataFrame) -> pd.DataFrame:
    return df_1m.resample("5min").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}
    ).dropna()


@dataclass
class Trade:
    direction: str
    entry: float
    exit: float
    pnl: float


def run_replay(df5: pd.DataFrame, regime: pd.Series, atr: pd.Series, mid: pd.Series, k: float, hold: int, scale: float) -> Dict[str, Any]:
    equity = 100000.0
    peak = equity
    max_dd = 0.0

    trades: List[Trade] = []
    pos: Optional[Dict[str, Any]] = None

    for i in range(len(df5)):
        bar = df5.iloc[i]

        # exit
        if pos is not None:
            pos["bars"] += 1
            if pos["bars"] >= hold:
                exit_px = float(bar["close"])
                entry_px = float(pos["entry"])
                direction = pos["dir"]
                pnl = (exit_px - entry_px) * scale if direction == "LONG" else (entry_px - exit_px) * scale
                equity += pnl
                trades.append(Trade(direction, entry_px, exit_px, pnl))
                pos = None

        # entry (only in MEAN_REVERTING)
        if pos is None:
            if regime.iloc[i] != MEAN_REVERTING:
                pass
            else:
                atr_val = float(atr.iloc[i])
                if pd.isna(atr_val) or atr_val <= 0:
                    pass
                else:
                    mid_val = float(mid.iloc[i])
                    close = float(bar["close"])

                    upper = mid_val + (k * atr_val)
                    lower = mid_val - (k * atr_val)

                    # fade extremes
                    if close > upper:
                        pos = {"dir": "SHORT", "entry": close, "bars": 0}
                    elif close < lower:
                        pos = {"dir": "LONG", "entry": close, "bars": 0}

        # DD tracking
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd

    wins = sum(1 for t in trades if t.pnl > 0)
    win_rate = (wins / len(trades) * 100.0) if trades else 0.0
    exp = sum(t.pnl for t in trades)

    return {
        "trades": len(trades),
        "win_rate": win_rate,
        "exp": exp,
        "max_dd_pct": max_dd * 100.0,
        "eq_end": equity,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path")
    ap.add_argument("--min", dest="kmin", type=float, required=True)
    ap.add_argument("--max", dest="kmax", type=float, required=True)
    ap.add_argument("--step", dest="kstep", type=float, required=True)
    ap.add_argument("--hold", type=int, required=True)
    ap.add_argument("--scale", type=float, default=100.0)
    ap.add_argument("--ema_mid", type=int, default=20)
    ap.add_argument("--atr_period", type=int, default=14)
    args = ap.parse_args()

    df = pd.read_csv(args.csv_path)
    df = _normalize(df)
    df5 = _to_5m(df)

    regime = classify_regime(df5)
    atr = _atr(df5, args.atr_period)
    mid = _ema(df5["close"], args.ema_mid)

    print("\n=== 5M MEAN REVERSION SWEEP (REGIME-GATED) ===")
    print(f"hold={args.hold}  scale={args.scale:.1f}  ema_mid={args.ema_mid}  atr_period={args.atr_period}")
    print(f"{'k_atr':>7}  {'trades':>6}  {'win%':>6}  {'exp':>10}  {'maxDD%':>8}  {'eq_end':>10}")

    k = args.kmin
    while k <= args.kmax + 1e-12:
        res = run_replay(df5, regime, atr, mid, k, args.hold, args.scale)
        print(f"{k:7.2f}  {res['trades']:6d}  {res['win_rate']:6.1f}  {res['exp']:10.2f}  {res['max_dd_pct']:8.3f}  {res['eq_end']:10.2f}")
        k += args.kstep

    print("\nSweep complete.")


if __name__ == "__main__":
    main()