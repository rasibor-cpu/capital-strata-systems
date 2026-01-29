"""
REA Capital — Data Adapters (Canonical)
======================================

Task 6.6C: Provide pluggable adapters for multiple CSV schemas + auto-detect.

Design:
- Everything downstream consumes canonical Bar(ts,o,h,l,c,v).
- Adapters handle schema quirks (headers, delimiters, date+time, angle-brackets).
- Auto-detect selects the best adapter by scoring header mapping and sample parse success.

Supported (examples):
- Standard OHLCV: ts_utc,o,h,l,c,v
- Common: time/open/high/low/close/volume
- MT5: DATE,TIME,OPEN,HIGH,LOW,CLOSE,TICKVOL
- MT5 angle: <DATE>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<TICKVOL>
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


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
    k = k.strip().lower()
    k = k.replace(" ", "_")
    return k


def sniff_delimiter(header_line: str) -> str:
    # Score common delimiters by count in header line
    candidates = [(",", header_line.count(",")), (";", header_line.count(";")), ("\t", header_line.count("\t"))]
    candidates.sort(key=lambda x: x[1], reverse=True)
    # If none found, default to comma
    return candidates[0][0] if candidates[0][1] > 0 else ","


def safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        s = str(x).strip()
        if s == "":
            return default
        return float(s)
    except Exception:
        return default


def parse_time_best_effort(s: str) -> datetime:
    s = (s or "").strip()
    # ISO-like first
    try:
        return datetime.fromisoformat(s.replace("Z", ""))
    except Exception:
        pass

    fmts = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y.%m.%d %H:%M:%S",
        "%Y.%m.%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y%m%d %H:%M:%S",
        "%Y%m%d %H:%M",
    ]
    for f in fmts:
        try:
            return datetime.strptime(s, f)
        except Exception:
            continue

    raise ValueError(f"Unparseable timestamp: {s!r}")


def parse_date_time_pair(date_s: str, time_s: str) -> datetime:
    ds = (date_s or "").strip()
    ts = (time_s or "").strip()

    fmts = [
        ("%Y.%m.%d", "%H:%M:%S"),
        ("%Y.%m.%d", "%H:%M"),
        ("%Y-%m-%d", "%H:%M:%S"),
        ("%Y-%m-%d", "%H:%M"),
        ("%Y/%m/%d", "%H:%M:%S"),
        ("%Y/%m/%d", "%H:%M"),
        ("%Y%m%d", "%H:%M:%S"),
        ("%Y%m%d", "%H:%M"),
    ]
    for df, tf in fmts:
        try:
            d = datetime.strptime(ds, df)
            t = datetime.strptime(ts, tf)
            return d.replace(hour=t.hour, minute=t.minute, second=t.second, microsecond=0)
        except Exception:
            continue

    # Fallback: join then parse best effort
    return parse_time_best_effort(f"{ds} {ts}")


# ----------------------------
# Adapter base
# ----------------------------

class BaseAdapter:
    name: str = "base"

    def score_header(self, header: List[str]) -> int:
        raise NotImplementedError

    def parse_row(self, row: Dict[str, str]) -> Bar:
        raise NotImplementedError


# ----------------------------
# Adapter: Standard OHLCV (ts_utc,o,h,l,c,v) and close variants
# ----------------------------

class StdOhlcvAdapter(BaseAdapter):
    name = "std_ohlcv"

    def score_header(self, header: List[str]) -> int:
        h = set(header)
        score = 0
        # timestamp
        if "ts_utc" in h:
            score += 5
        if "ts" in h or "datetime" in h or "timestamp" in h or "time" in h:
            score += 3
        # ohlc
        for k in ("o", "h", "l", "c"):
            if k in h:
                score += 2
        # volume
        if "v" in h or "volume" in h or "vol" in h:
            score += 1
        return score

    def parse_row(self, row: Dict[str, str]) -> Bar:
        # timestamp keys preference
        if "ts_utc" in row and row["ts_utc"].strip():
            ts = parse_time_best_effort(row["ts_utc"])
        elif "ts" in row and row["ts"].strip():
            ts = parse_time_best_effort(row["ts"])
        elif "datetime" in row and row["datetime"].strip():
            ts = parse_time_best_effort(row["datetime"])
        elif "timestamp" in row and row["timestamp"].strip():
            ts = parse_time_best_effort(row["timestamp"])
        elif "time" in row and row["time"].strip():
            ts = parse_time_best_effort(row["time"])
        else:
            raise ValueError("no timestamp key found")

        o = safe_float(row.get("o", row.get("open", "")))
        h = safe_float(row.get("h", row.get("high", "")))
        l = safe_float(row.get("l", row.get("low", "")))
        c = safe_float(row.get("c", row.get("close", "")))
        v = safe_float(row.get("v", row.get("volume", row.get("vol", ""))), 0.0)
        return Bar(ts=ts, o=o, h=h, l=l, c=c, v=v)


# ----------------------------
# Adapter: Generic (time/open/high/low/close[/volume])
# ----------------------------

class GenericOhlcAdapter(BaseAdapter):
    name = "generic_ohlc"

    def score_header(self, header: List[str]) -> int:
        h = set(header)
        score = 0
        if any(k in h for k in ("time", "timestamp", "datetime", "date", "dt")):
            score += 4
        if all(k in h for k in ("open", "high", "low", "close")):
            score += 6
        if any(k in h for k in ("volume", "vol", "tick_volume", "tickvol")):
            score += 1
        return score

    def parse_row(self, row: Dict[str, str]) -> Bar:
        # timestamp
        for k in ("datetime", "timestamp", "time", "dt"):
            if k in row and row[k].strip():
                ts = parse_time_best_effort(row[k])
                break
        else:
            # sometimes "date" contains full datetime
            if "date" in row and row["date"].strip():
                ts = parse_time_best_effort(row["date"])
            else:
                raise ValueError("no timestamp key found")

        o = safe_float(row.get("open", ""))
        h = safe_float(row.get("high", ""))
        l = safe_float(row.get("low", ""))
        c = safe_float(row.get("close", ""))

        # volume preferences
        v_key = None
        for k in ("tick_volume", "tickvol", "volume", "vol"):
            if k in row and row[k].strip():
                v_key = k
                break
        v = safe_float(row.get(v_key, ""), 0.0) if v_key else 0.0

        return Bar(ts=ts, o=o, h=h, l=l, c=c, v=v)


# ----------------------------
# Adapter: MT5 (DATE+TIME, OPEN/HIGH/LOW/CLOSE)
# ----------------------------

class Mt5CsvAdapter(BaseAdapter):
    name = "mt5_csv"

    def score_header(self, header: List[str]) -> int:
        h = set(header)
        score = 0
        # date+time pair
        if "date" in h and "time" in h:
            score += 6
        # ohlc
        if all(k in h for k in ("open", "high", "low", "close")):
            score += 6
        # tick volume (optional)
        if "tickvol" in h or "tick_volume" in h:
            score += 2
        if "vol" in h or "volume" in h:
            score += 1
        return score

    def parse_row(self, row: Dict[str, str]) -> Bar:
        if "date" not in row or "time" not in row:
            raise ValueError("mt5 requires date+time")
        ts = parse_date_time_pair(row["date"], row["time"])
        o = safe_float(row.get("open", ""))
        h = safe_float(row.get("high", ""))
        l = safe_float(row.get("low", ""))
        c = safe_float(row.get("close", ""))

        # MT5 often provides tickvol and vol
        v_key = None
        for k in ("tickvol", "tick_volume", "vol", "volume"):
            if k in row and row[k].strip():
                v_key = k
                break
        v = safe_float(row.get(v_key, ""), 0.0) if v_key else 0.0

        return Bar(ts=ts, o=o, h=h, l=l, c=c, v=v)


# ----------------------------
# Adapter selection + load
# ----------------------------

ADAPTERS: List[BaseAdapter] = [
    StdOhlcvAdapter(),
    Mt5CsvAdapter(),
    GenericOhlcAdapter(),
]


def choose_adapter(header: List[str], adapter_name: str = "auto") -> BaseAdapter:
    if adapter_name != "auto":
        for a in ADAPTERS:
            if a.name == adapter_name:
                return a
        raise ValueError(f"Unknown adapter: {adapter_name}. Options: {[a.name for a in ADAPTERS]}")

    # auto: score adapters
    scored = [(a.score_header(header), a) for a in ADAPTERS]
    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best = scored[0]
    if best_score <= 0:
        raise ValueError(f"Could not auto-detect adapter for header={header}. Options: {[a.name for a in ADAPTERS]}")
    return best


def load_bars_from_csv(
    csv_path: str,
    counters: Dict[str, Any],
    adapter_name: str = "auto",
    max_rows_probe: int = 10,
) -> Tuple[List[Bar], str, str]:
    """
    Returns: (bars, adapter_used, delimiter_used)
    Counters updated:
      - exceptions_count
      - nan_or_inf_count
      - bars_1m_total
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    counters.setdefault("exceptions_count", 0)
    counters.setdefault("nan_or_inf_count", 0)

    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        # sniff delimiter from first line
        first_line = f.readline()
        if not first_line:
            raise ValueError("CSV is empty")
        delim = sniff_delimiter(first_line)

        # rewind and use DictReader
        f.seek(0)
        reader = csv.DictReader(f, delimiter=delim)
        if not reader.fieldnames:
            raise ValueError("CSV has no header row")

        # normalize headers
        norm_fields = [norm_key(x) for x in reader.fieldnames]
        reader.fieldnames = norm_fields  # type: ignore

        adapter = choose_adapter(norm_fields, adapter_name=adapter_name)
        bars: List[Bar] = []

        for row in reader:
            try:
                r = {norm_key(k): (v if v is not None else "") for k, v in row.items()}
                b = adapter.parse_row(r)

                # NaN guard
                if any(x != x for x in (b.o, b.h, b.l, b.c, b.v)):
                    counters["nan_or_inf_count"] += 1
                    continue

                bars.append(b)
            except Exception:
                counters["exceptions_count"] += 1
                continue

    bars.sort(key=lambda b: b.ts)
    counters["bars_1m_total"] = len(bars)
    return bars, adapter.name, delim