"""
make_5m_from_long.py
Build sample_spy_5m.csv from sample_spy_1m_long.csv (preferred).
Produces enough 5m bars for RegimeGate (target >= 40).
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
        v = row.get(k)
        if v not in (None, ""):
            return v
    return None


def floor_to_5m(dt: datetime) -> datetime:
    minute = (dt.minute // 5) * 5
    return dt.replace(minute=minute, second=0, microsecond=0)


def main() -> int:
    inp = "sample_spy_1m_long.csv"
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
            if ts >= buckets[key]["last_ts"]:
                buckets[key]["last_close"] = close
                buckets[key]["last_ts"] = ts
            buckets[key]["volume"] += vol

    ordered: List[Dict[str, Any]] = [buckets[k] for k in sorted(buckets.keys())]

    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ts_utc", "close", "volume"])
        w.writeheader()
        for it in ordered:
            w.writerow({"ts_utc": it["ts_utc"], "close": it["last_close"], "volume": round(float(it["volume"]), 6)})

    print(f"[OK] Wrote {len(ordered)} bars to {out}")
    print("[Target] Need >= 40 bars for RegimeGate to allow.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())