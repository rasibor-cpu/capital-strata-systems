from __future__ import annotations

"""
MT5 Bar Feed (CSV) -> Rolling Mean/VWAP proxy

Goal:
- Remove manual VWAP entry
- Use a CSV export from MT5 (OHLC bars) to compute a rolling "mean" level
- Volume is often unavailable, so we compute a VWAP-proxy as a rolling average of typical price:
    typical = (H + L + C) / 3
    mean_level = rolling_average(typical, lookback)

CSV expectations (flexible):
- Must contain a time column + at least Close, ideally High/Low too.
- Common headers supported:
  time, datetime, date, ts, ts_utc
  close, c
  high, h
  low, l

If only Close exists, we use Close as typical.
"""

import csv
import os
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple


TIME_KEYS = ("time", "datetime", "date", "timestamp", "ts", "ts_utc", "tsutc")
CLOSE_KEYS = ("close", "c", "last", "price")
HIGH_KEYS = ("high", "h")
LOW_KEYS = ("low", "l")


def _norm(s: str) -> str:
    return "".join(ch.lower() for ch in s.strip() if ch.isalnum() or ch in ("_",))


def _pick_col(fieldnames: List[str], keys: Tuple[str, ...]) -> Optional[str]:
    m = {_norm(x): x for x in fieldnames}
    for k in keys:
        kk = _norm(k)
        if kk in m:
            return m[kk]
    return None


def _to_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    s = str(x).strip().replace(",", "")
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None


@dataclass
class RollingMeanResult:
    last_close: float
    mean_level: float
    bars_used: int


def compute_rolling_mean_from_mt5_csv(
    csv_path: str,
    lookback: int = 30
) -> RollingMeanResult:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"MT5 CSV not found: {csv_path}")

    # MT5 exports sometimes use ';' delimiter depending on locale.
    # We'll sniff quickly.
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        sample = f.read(2048)
        delim = ";" if sample.count(";") > sample.count(",") else ","

    rows: List[Dict[str, Any]] = []
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f, delimiter=delim)
        if not r.fieldnames:
            raise ValueError("CSV has no header row.")
        fn = r.fieldnames

        c_time = _pick_col(fn, TIME_KEYS)  # not strictly needed for calc
        c_close = _pick_col(fn, CLOSE_KEYS)
        c_high = _pick_col(fn, HIGH_KEYS)
        c_low = _pick_col(fn, LOW_KEYS)

        if not c_close:
            raise ValueError(f"Could not find Close column in CSV headers: {fn}")

        for row in r:
            close = _to_float(row.get(c_close))
            if close is None:
                continue
            high = _to_float(row.get(c_high)) if c_high else None
            low = _to_float(row.get(c_low)) if c_low else None

            # Typical price if H/L available; else close.
            if high is not None and low is not None:
                typical = (high + low + close) / 3.0
            else:
                typical = close

            rows.append({"close": close, "typical": typical, "t": row.get(c_time) if c_time else ""})

    if len(rows) < 2:
        raise ValueError("Not enough bars in CSV to compute mean.")

    lookback = max(2, int(lookback))
    window = rows[-lookback:] if len(rows) >= lookback else rows[:]
    mean_level = sum(x["typical"] for x in window) / float(len(window))
    last_close = float(rows[-1]["close"])

    return RollingMeanResult(
        last_close=last_close,
        mean_level=float(mean_level),
        bars_used=len(window)
    )