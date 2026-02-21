"""
tools/download_spy_1m.py

Robust chunked 1-minute downloader via yfinance.

Reality:
- Yahoo often restricts 1m history to ~30 days max.
- Per-request window is also limited (~7 days typical).
So we:
- enforce days <= 30
- download in chunk_days windows
- flatten MultiIndex tuple columns safely
- stitch and save to CSV with canonical columns: ts_utc,o,h,l,c,v

Usage:
  python tools/download_spy_1m.py --days 30 --chunk_days 5 --out spy_1m_30d.csv
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

import pandas as pd
import yfinance as yf


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    # yfinance can return MultiIndex columns like ('Open','SPY')
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = ["_".join([str(x) for x in tup if x is not None and str(x) != ""]).strip("_") for tup in df.columns]
    return df


def _pick_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    cols = list(df.columns)
    low = {str(c).lower(): c for c in cols}
    for cand in candidates:
        if cand in low:
            return low[cand]
    return None


def _download_chunk(symbol: str, start_utc: datetime, end_utc: datetime) -> pd.DataFrame:
    df = yf.download(
        symbol,
        start=start_utc,
        end=end_utc,
        interval="1m",
        auto_adjust=False,
        progress=False,
        threads=False,
    )

    if df is None or df.empty:
        return pd.DataFrame()

    df = _flatten_columns(df).reset_index()

    dt_col = _pick_col(df, ["datetime", "date"])
    if dt_col is None:
        # Usually first column after reset_index
        dt_col = df.columns[0]

    o = _pick_col(df, ["open", f"open_{symbol.lower()}"])
    h = _pick_col(df, ["high", f"high_{symbol.lower()}"])
    l = _pick_col(df, ["low", f"low_{symbol.lower()}"])
    c = _pick_col(df, ["close", f"close_{symbol.lower()}"])
    v = _pick_col(df, ["volume", f"volume_{symbol.lower()}"])

    if None in [o, h, l, c]:
        # Fall back: try partial matches
        def find_contains(key: str) -> str | None:
            for col in df.columns:
                if key in str(col).lower():
                    return col
            return None
        o = o or find_contains("open")
        h = h or find_contains("high")
        l = l or find_contains("low")
        c = c or find_contains("close")
        v = v or find_contains("volume")

    if None in [o, h, l, c]:
        raise RuntimeError(f"Could not locate OHLC columns in yfinance output columns={list(df.columns)}")

    out = pd.DataFrame({
        "ts_utc": pd.to_datetime(df[dt_col], utc=True, errors="coerce"),
        "o": df[o],
        "h": df[h],
        "l": df[l],
        "c": df[c],
        "v": df[v] if v is not None else 0,
    }).dropna(subset=["ts_utc"])

    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="SPY")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--chunk_days", type=int, default=5)
    ap.add_argument("--out", default="spy_1m_30d.csv")
    args = ap.parse_args()

    if args.days > 30:
        raise SystemExit("Yahoo 1m data is typically limited to the last 30 days. Re-run with --days 30 (or less).")

    end = _utc_now()
    start = end - timedelta(days=args.days)

    chunks = []
    cursor = start

    print(f"Downloading {args.symbol} 1m: days={args.days}, chunk={args.chunk_days}d")
    while cursor < end:
        chunk_end = min(cursor + timedelta(days=args.chunk_days), end)
        print(f"  chunk {cursor.isoformat()} -> {chunk_end.isoformat()} ...", end="")

        part = _download_chunk(args.symbol, cursor, chunk_end)
        if part.empty:
            print(" empty")
        else:
            print(f" ok ({len(part)} rows)")
            chunks.append(part)

        cursor = chunk_end

    if not chunks:
        raise RuntimeError("No data downloaded. If market is closed or Yahoo is restricting 1m, try again later or use another data source.")

    df = pd.concat(chunks, ignore_index=True)
    df = df.drop_duplicates(subset=["ts_utc"]).sort_values("ts_utc")

    df.to_csv(args.out, index=False)
    print(f"\nSaved: {args.out}  rows={len(df)}  from={df['ts_utc'].min()}  to={df['ts_utc'].max()}")


if __name__ == "__main__":
    main()