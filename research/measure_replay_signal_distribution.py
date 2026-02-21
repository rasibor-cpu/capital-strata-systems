"""
Measure Replay Signal Distribution (CSV) - SAFE
----------------------------------------------
Computes the distribution of the replay "momentum_signal" values:

sig = clamp(delta * scale, -1, +1)
delta = (px - prev_px) / prev_px

Supports header OHLCV like: ts_utc,o,h,l,c,v
Uses close column by default (c or close).

Run:
  python -m tools.measure_replay_signal_distribution sample_spy_1m_long.csv --scale 50

Outputs:
- n, min, max, mean
- p50, p75, p90, p95, p99
"""

from __future__ import annotations

import sys
import os
import csv
import argparse
from typing import List

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _norm(s: str) -> str:
    return s.replace("\ufeff", "").strip().lower()


def load_close_series(path: str) -> List[float]:
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        first = next(reader, None)
        if not first:
            raise ValueError("CSV is empty")

        # Detect header
        has_header = not (first[0][:1].isdigit())

        closes: List[float] = []

        if has_header:
            # Map header fields
            headers = [_norm(x) for x in first]
            # close candidates
            close_keys = ["close", "c", "adj_close", "last", "price"]
            close_idx = next((i for i, h in enumerate(headers) if h in close_keys), None)
            if close_idx is None:
                raise ValueError(f"Could not find close/price column in headers: {headers}")

            for row in reader:
                if not row or len(row) <= close_idx:
                    continue
                closes.append(float(row[close_idx]))

        else:
            # first row is data; assume OHLCV no-header -> close at index 4
            # or 2-col no-header -> price at index 1
            def parse_row(row):
                if len(row) >= 5:
                    return float(row[4])
                if len(row) >= 2:
                    return float(row[1])
                return None

            c0 = parse_row(first)
            if c0 is not None:
                closes.append(c0)

            for row in reader:
                c = parse_row(row)
                if c is not None:
                    closes.append(c)

        if len(closes) < 3:
            raise ValueError("Need at least 3 close prices")
        return closes


def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def pct(sorted_vals: List[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = int(round((p / 100.0) * (len(sorted_vals) - 1)))
    idx = max(0, min(idx, len(sorted_vals) - 1))
    return sorted_vals[idx]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path", type=str)
    ap.add_argument("--scale", type=float, default=50.0)
    args = ap.parse_args()

    closes = load_close_series(args.csv_path)

    sigs: List[float] = []
    prev = closes[0]
    for px in closes[1:]:
        if prev <= 0:
            sig = 0.0
        else:
            delta = (px - prev) / prev
            sig = clamp(delta * args.scale, -1.0, 1.0)
        sigs.append(sig)
        prev = px

    sigs_sorted = sorted(sigs)
    n = len(sigs_sorted)
    mean = sum(sigs_sorted) / n

    print("\n=== REPLAY SIGNAL DISTRIBUTION ===")
    print(f"file={args.csv_path}")
    print(f"scale={args.scale}")
    print(f"n={n}")
    print(f"min={sigs_sorted[0]:.6f}  mean={mean:.6f}  max={sigs_sorted[-1]:.6f}")
    print(
        "p50={:.6f}  p75={:.6f}  p90={:.6f}  p95={:.6f}  p99={:.6f}".format(
            pct(sigs_sorted, 50),
            pct(sigs_sorted, 75),
            pct(sigs_sorted, 90),
            pct(sigs_sorted, 95),
            pct(sigs_sorted, 99),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())