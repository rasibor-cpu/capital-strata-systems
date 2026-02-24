"""
tools/build_h1_from_m5.py

Build H1 close series from M5 CSV (timestamp,price).

Handles weird timestamp:
  2025-02-23T22:00:00:00.000000000Z
(normalizes to)
  2025-02-23T22:00:00.000000000Z
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path


def normalize_ts(ts: str) -> str:
    ts = ts.strip().replace("\ufeff", "")
    if ts.endswith("Z"):
        ts = ts[:-1]

    # Drop fractional seconds (we don't need them)
    if "." in ts:
        left = ts.split(".", 1)[0]
    else:
        left = ts

    # Fix the extra ":00" after seconds:
    # left expected: YYYY-MM-DDTHH:MM:SS
    # but we may have: YYYY-MM-DDTHH:MM:SS:FF
    if "T" in left:
        date_part, time_part = left.split("T", 1)
        parts = time_part.split(":")
        if len(parts) >= 3:
            # keep only HH:MM:SS
            time_part = ":".join(parts[:3])
        left = f"{date_part}T{time_part}"

    return left


def parse_timestamp(ts: str) -> datetime:
    left = normalize_ts(ts)

    if "T" in left:
        return datetime.strptime(left, "%Y-%m-%dT%H:%M:%S")
    else:
        return datetime.strptime(left, "%Y-%m-%d %H:%M:%S")


def hour_bucket(dt: datetime) -> datetime:
    return dt.replace(minute=0, second=0, microsecond=0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in_csv", required=True)
    ap.add_argument("--out_csv", required=True)
    args = ap.parse_args()

    in_path = Path(args.in_csv)
    out_path = Path(args.out_csv)

    buckets = {}  # hour_dt -> (last_dt, last_close)

    with open(in_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    # skip header
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue

        parts = line.split(",")
        if len(parts) < 2:
            continue

        ts_raw = parts[0]
        price_raw = parts[1]

        try:
            dt = parse_timestamp(ts_raw)
            price = float(price_raw)
        except Exception:
            continue

        h = hour_bucket(dt)
        prev = buckets.get(h)
        if prev is None or dt >= prev[0]:
            buckets[h] = (dt, price)

    hours = sorted(buckets.keys())
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("timestamp,close\n")
        for h in hours:
            _, price = buckets[h]
            f.write(f"{h.strftime('%Y-%m-%d %H:%M:%S')},{price:.8f}\n")

    print(f"Built H1 rows: {len(hours)}")
    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()