"""
tools/regime_window_scan.py

Scan a CSV and report TOP intraday windows with the most TRENDING_UP / TRENDING_DOWN bars.
Works even if the CSV contains only 1 day.

Usage:
  python -m tools.regime_window_scan sample_spy_1m_long.csv --window 60 --top 10
  python -m tools.regime_window_scan sample_spy_1m_long.csv --window 90 --top 10
"""

from __future__ import annotations

import argparse
import pandas as pd

from engine.regime.regime_classifier import (
    classify_regime,
    TRENDING_UP,
    TRENDING_DOWN,
    MEAN_REVERTING,
    NEUTRAL,
)


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path")
    ap.add_argument("--window", type=int, default=60, help="Window size in minutes")
    ap.add_argument("--top", type=int, default=10)
    args = ap.parse_args()

    df = pd.read_csv(args.csv_path)
    df = _normalize(df)
    df5 = _to_5m(df)

    regime = classify_regime(df5)
    tmp = pd.DataFrame({"regime": regime}, index=df5.index)

    # Window is in minutes; df5 is 5-minute bars
    bars = max(1, args.window // 5)

    rows = []
    for i in range(0, len(tmp) - bars + 1):
        w = tmp.iloc[i:i + bars]
        start = w.index[0]
        end = w.index[-1]
        counts = w["regime"].value_counts()

        rows.append({
            "start": start,
            "end": end,
            TRENDING_UP: int(counts.get(TRENDING_UP, 0)),
            TRENDING_DOWN: int(counts.get(TRENDING_DOWN, 0)),
            MEAN_REVERTING: int(counts.get(MEAN_REVERTING, 0)),
            NEUTRAL: int(counts.get(NEUTRAL, 0)),
            "total_5m_bars": len(w),
        })

    out = pd.DataFrame(rows)

    top_up = out.sort_values([TRENDING_UP, TRENDING_DOWN, MEAN_REVERTING], ascending=False).head(args.top)
    top_dn = out.sort_values([TRENDING_DOWN, TRENDING_UP, MEAN_REVERTING], ascending=False).head(args.top)

    print(f"\n=== TOP TRENDING_UP WINDOWS ({args.window} min) ===")
    print(top_up.to_string(index=False))

    print(f"\n=== TOP TRENDING_DOWN WINDOWS ({args.window} min) ===")
    print(top_dn.to_string(index=False))


if __name__ == "__main__":
    main()