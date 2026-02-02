"""
make_5m_csv.py
Create a 5-minute OHLCV CSV from an existing 1-minute CSV.

Input expected columns (any of these):
- timestamp OR ts_utc
- close OR c
- volume OR v  (optional)

Output:
- sample_spy_5m.csv with columns: ts_utc, close, volume
(We keep it minimal because RegimeGate only needs bars_5m and as_of_utc;
your gate may use more fields later, but this gets us unblocked today.)
"""

from __future__ import annotations

import csv
from datetime import datetime
from typing import Optional, Dict, Any, List


def parse_ts(s: str) -> Optional[datetime]:
    s = (s or "").strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except Exception:
        return None


def pick(row: Dict[str, str], *keys: str) -> Optional[str]:
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return row[k]
    return None


def floor_to_5m(dt: datetime) -> datetime:
    # floor to 5-minute boundary
    minute = (dt.minute // 5) * 5
    return dt.replace(minute=minute, second=0, microsecond=0)


def main() -> int:
    inp = "sample_spy_1m.csv"
    out = "sample_spy_5m.csv"

    try:
        with open(inp, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except FileNotFoundError:
        print(f"[ERROR] Missing input file: {inp}")
        return 2

    if not rows:
        print("[ERROR] Input CSV is empty.")
        return 3

    # Aggregate 1m → 5m (we keep close=last close, volume=sum volume)
    buckets: Dict[str, Dict[str, Any]] = {}

    for r in rows:
        ts_s = pick(r, "ts_utc", "timestamp")
        close_s = pick(r, "close", "c")
        vol_s = pick(r, "volume", "v")

        if not ts_s or not close_s:
            continue

        ts = parse_ts(ts_s)
        if ts is None:
            continue

        b = floor_to_5m(ts)
        key = b.isoformat()

        close = float(close_s)
        vol = float(vol_s) if vol_s else 1.0

        if key not in buckets:
            buckets[key] = {"ts_utc": key, "last_close": close, "volume": vol, "last_ts": ts}
        else:
            # update last close if newer
            if ts >= buckets[key]["last_ts"]:
                buckets[key]["last_close"] = close
                buckets[key]["last_ts"] = ts
            buckets[key]["volume"] += vol

    # Sort buckets by time
    ordered: List[Dict[str, Any]] = [buckets[k] for k in sorted(buckets.keys())]

    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ts_utc", "close", "volume"])
        w.writeheader()
        for it in ordered:
            w.writerow({"ts_utc": it["ts_utc"], "close": it["last_close"], "volume": round(float(it["volume"]), 6)})

    print(f"[OK] Wrote {len(ordered)} bars to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())