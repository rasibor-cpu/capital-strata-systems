"""Fetch real historical candles into the local cache (read-only market data).

Usage:
  python tools/css_fetch_candles.py --source coinbase --instrument BTC-USD --granularity 3600 --bars 8000 \
      --cache data/market_cache
  OANDA_PRACTICE_TOKEN=... python tools/css_fetch_candles.py --source oanda --instrument EUR_USD ...

Pages backwards from now, merges, validates and stores CSV + SHA-256. Never places orders.
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.signals.candles import (  # noqa: E402
    CoinbasePublicCandles,
    CsvCandleStore,
    OandaPracticeCandles,
    merge,
    validate,
)


def fetch_history(provider, instrument: str, granularity_s: int, bars: int, *, sleep_s: float = 0.35):
    parts, end, have = [], datetime.now(timezone.utc), 0
    while have < bars:
        part = provider.fetch(instrument, granularity_s=granularity_s, end=end)
        if not part.candles:
            break
        parts.append(part)
        have = len(merge(parts).candles)
        oldest = part.candles[0].ts
        if datetime.fromtimestamp(oldest, tz=timezone.utc) >= end:
            break
        end = datetime.fromtimestamp(oldest, tz=timezone.utc)
        time.sleep(sleep_s)
    series = merge(parts)
    series = type(series)(series.instrument, series.asset_class, series.granularity_s, series.source,
                          series.candles[-bars:])
    return validate(series, allow_gaps=10_000)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["coinbase", "oanda"], required=True)
    ap.add_argument("--instrument", required=True)
    ap.add_argument("--granularity", type=int, default=3600)
    ap.add_argument("--bars", type=int, default=8000)
    ap.add_argument("--cache", default="data/market_cache")
    args = ap.parse_args(argv)
    provider = CoinbasePublicCandles() if args.source == "coinbase" else OandaPracticeCandles()
    series = fetch_history(provider, args.instrument, args.granularity, args.bars)
    path = CsvCandleStore(args.cache).save(series)
    print(f"{series.instrument} {series.source} bars={len(series.candles)} sha256={series.digest} -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
