"""
tools/regime_scan.py

Scan a CSV and report regime counts by day (5m bars),
so we can pick strong TRENDING_UP / TRENDING_DOWN days for breakout testing.

Usage:
  python -m tools.regime_scan sample_spy_1m_long.csv
  python -m tools.regime_scan sample_spy_1m_long.csv --top 10
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
    df5 = df_1m.resample("5min").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}
    ).dropna()
    return df5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path")
    ap.add_argument("--top", type=int, default=10)
    args = ap.parse_args()

    df = pd.read_csv(args.csv_path)
    df = _normalize(df)
    df5 = _to_5m(df)

    regime = classify_regime(df5)
    daily = pd.DataFrame({"regime": regime})
    daily["day"] = daily.index.date

    pivot = (
        daily.groupby(["day", "regime"])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )

    for col in [TRENDING_UP, TRENDING_DOWN, MEAN_REVERTING, NEUTRAL]:
        if col not in pivot.columns:
            pivot[col] = 0

    pivot["total_5m_bars"] = pivot[TRENDING_UP] + pivot[TRENDING_DOWN] + pivot[MEAN_REVERTING] + pivot[NEUTRAL]

    top_up = pivot.sort_values([TRENDING_UP, "total_5m_bars"], ascending=False).head(args.top)
    top_dn = pivot.sort_values([TRENDING_DOWN, "total_5m_bars"], ascending=False).head(args.top)

    print("\n=== TOP TRENDING_UP DAYS ===")
    print(top_up[["day", TRENDING_UP, TRENDING_DOWN, MEAN_REVERTING, NEUTRAL, "total_5m_bars"]].to_string(index=False))

    print("\n=== TOP TRENDING_DOWN DAYS ===")
    print(top_dn[["day", TRENDING_UP, TRENDING_DOWN, MEAN_REVERTING, NEUTRAL, "total_5m_bars"]].to_string(index=False))


if __name__ == "__main__":
    main()