"""
REA Capital — Data Adapters (Canonical)
======================================

Task 6.6C: Provide pluggable adapters for multiple CSV schemas + auto-detect.

Design:
- Everything downstream consumes canonical Bar(ts,o,h,l,c,v).
- Adapters handle schema quirks (headers, delimiters, date+time, angle-brackets).
- Auto-detect selects the best adapter by scoring header mapping.

Supported:
- Standard OHLCV: ts_utc,o,h,l,c,v
- Generic OHLC: time/open/high/low/close[/volume]
- MT5 CSV: DATE,TIME,OPEN,HIGH,LOW,CLOSE,TICKVOL
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Tuple


# ----------------------------
# Canonical bar
# ----------------------------

@dataclass
class Bar:
    ts: datetime
    o: float
    h: float
    l: float
    c: float
    v: float = 0.0


# ----------------------------
# Normalization helpers
# ----------------------------

def norm_key(k: str) -> str:
    k = (k or "").strip()
    if k.startswith("<") and k.endswith(">"):
        k = k[1:-1].strip()
    return k.lower().replace(" ", "_")


def sniff_delimiter(header_line: str) -> str:
    candidates = [(",", header_line.count(",")), (";", header_line.count(";")), ("\t", header_line.count("\t"))]
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[0][0] if candidates[0][1] > 0 else ","


def safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def parse_time_best_effort(s: str) -> datetime:
    s = s.strip().replace("Z", "")
    try:
        return datetime.fromisoformat(s)
    except Exception:
        pass

    fmts = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y.%m.%d %H:%M:%S",
        "%Y.%m.%d %H:%M",
    ]
    for f in fmts:
        try:
            return datetime.strptime(s, f)
        except Exception:
            continue

    raise ValueError(f"Unparseable timestamp: {s}")


def parse_date_time_pair(d: str, t: str) -> datetime:
    return parse_time_best_effort(f"{d} {t}")


# ----------------------------
# Adapter base
# ----------------------------

class BaseAdapter:
    name = "base"

    def score_header(self, header: List[str]) -> int:
        raise NotImplementedError

    def parse_row(self, row: Dict[str, str]) -> Bar:
        raise NotImplementedError


# ----------------------------
# Standard OHLCV adapter
# ----------------------------

class StdOhlcvAdapter(BaseAdapter):
    name = "std_ohlcv"

    def score_header(self, h: List[str]) -> int:
        score = 0
        if "ts_utc" in h:
            score += 5
        for k in ("o", "h", "l", "c"):
            if k in h:
                score += 2
        if "v" in h:
            score += 1
        return score

    def parse_row(self, r: Dict[str, str]) -> Bar:
        ts = parse_time_best_effort(r["ts_utc"])
        return Bar(
            ts=ts,
            o=safe_float(r["o"]),
            h=safe_float(r["h"]),
            l=safe_float(r["l"]),
            c=safe_float(r["c"]),
            v=safe_float(r.get("v", 0.0)),
        )


# ----------------------------
# Generic OHLC adapter
# ----------------------------

class GenericOhlcAdapter(BaseAdapter):
    name = "generic_ohlc"

    def score_header(self, h: List[str]) -> int:
        return 10 if all(k in h for k in ("open", "high", "low", "close")) else 0

    def parse_row(self, r: Dict[str, str]) -> Bar:
        ts = parse_time_best_effort(r.get("time") or r.get("timestamp") or r.get("datetime"))
        return Bar(
            ts=ts,
            o=safe_float(r["open"]),
            h=safe_float(r["high"]),
            l=safe_float(r["low"]),
            c=safe_float(r["close"]),
            v=safe_float(r.get("volume", 0.0)),
        )


# ----------------------------
# MT5 adapter
# ----------------------------

class Mt5CsvAdapter(BaseAdapter):
    name = "mt5_csv"

    def score_header(self, h: List[str]) -> int:
        return 12 if "date" in h and "time" in h else 0

    def parse_row(self, r: Dict[str, str]) -> Bar:
        ts = parse_date_time_pair(r["date"], r["time"])
        return Bar(
            ts=ts,
            o=safe_float(r["open"]),
            h=safe_float(r["high"]),
            l=safe_float(r["low"]),
            c=safe_float(r["close"]),
            v=safe_float(r.get("tickvol", r.get("volume", 0.0))),
        )


# ----------------------------
# Adapter selection + loader
# ----------------------------

ADAPTERS = [StdOhlcvAdapter(), Mt5CsvAdapter(), GenericOhlcAdapter()]


def choose_adapter(header: List[str], name: str) -> BaseAdapter:
    if name != "auto":
        for a in ADAPTERS:
            if a.name == name:
                return a
        raise ValueError(f"Unknown adapter: {name}")

    scored = [(a.score_header(header), a) for a in ADAPTERS]
    scored.sort(key=lambda x: x[0], reverse=True)
    if scored[0][0] <= 0:
        raise ValueError(f"Could not auto-detect adapter for header={header}")
    return scored[0][1]


def load_bars_from_csv(
    csv_path: str,
    counters: Dict[str, Any],
    adapter_name: str = "auto",
) -> Tuple[List[Bar], str, str]:

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    counters.setdefault("exceptions_count", 0)
    counters.setdefault("nan_or_inf_count", 0)

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        first = f.readline()
        delim = sniff_delimiter(first)
        f.seek(0)

        reader = csv.DictReader(f, delimiter=delim)
        header = [norm_key(x) for x in reader.fieldnames or []]
        reader.fieldnames = header

        adapter = choose_adapter(header, adapter_name)
        bars: List[Bar] = []

        for row in reader:
            try:
                r = {norm_key(k): v for k, v in row.items()}
                bar = adapter.parse_row(r)
                bars.append(bar)
            except Exception:
                counters["exceptions_count"] += 1

    bars.sort(key=lambda b: b.ts)
    counters["bars_1m_total"] = len(bars)
    return bars, adapter.name, delim