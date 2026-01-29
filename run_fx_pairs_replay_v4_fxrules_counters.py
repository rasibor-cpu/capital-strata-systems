"""
REA Capital — FX Pairs Replay (v4) + FX Rules + Counters  [ANALYSIS-ONLY]
=======================================================================

Task 6.6A: Extend CSV loader to support MT5/broker-style CSV schemas, then print
canonical counters summary via counters_summary.py.

SAFETY CONSTRAINTS
------------------
- ANALYSIS-ONLY: no MT5, no broker, no execution. Replay + metrics only.

Supported CSV Schemas (best-effort)
-----------------------------------
1) Single datetime column + OHLC:
   time|timestamp|datetime|date  +  open|high|low|close

2) MT5-style separate DATE + TIME columns:
   date + time + open + high + low + close

3) MT5/broker "angle bracket" headers:
   <DATE>, <TIME>, <OPEN>, <HIGH>, <LOW>, <CLOSE>, <TICKVOL>, <VOL>, <SPREAD>
   Also supports <DATETIME> as a single combined timestamp.

4) Common variants:
   - Tick Volume column names: tick_volume, tickvol, tick volume, <TICKVOL>
   - Volume column names: volume, vol, <VOL>

If a row cannot be parsed, it is counted as an exception and skipped.

Usage:
------
python run_fx_pairs_replay_v4_fxrules_counters.py --csv data_fx\\EUR_USD_1m.csv --symbol EURUSD
python run_fx_pairs_replay_v4_fxrules_counters.py --csv data_fx\\EUR_USD_1m.csv --symbol EURUSD --min5 40
"""

from __future__ import annotations

import argparse
import csv
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# Canonical summary formatter (Task 6.3)
from counters_summary import print_summary

# Optional FX rules module (promoted earlier)
FX_RULES_AVAILABLE = True
try:
    from regime.fx_rules import FXRules  # type: ignore
except Exception:
    FX_RULES_AVAILABLE = False


# ----------------------------
# Data structures
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
# CSV header normalization
# ----------------------------

def _norm_key(k: str) -> str:
    """
    Normalize CSV header keys:
    - trim
    - lowercase
    - remove surrounding angle brackets
    - collapse spaces to underscore
    """
    k = (k or "").strip()
    if k.startswith("<") and k.endswith(">"):
        k = k[1:-1].strip()
    k = k.lower().strip()
    k = k.replace(" ", "_")
    return k


_TIME_KEYS = ("time", "timestamp", "datetime", "date", "dt")
_DATE_KEYS = ("date",)
_TIME_ONLY_KEYS = ("time",)
_DATETIME_KEYS = ("datetime", "timestamp", "dt")

_OHLC_KEYS = {
    "open": ("open", "o"),
    "high": ("high", "h"),
    "low": ("low", "l"),
    "close": ("close", "c"),
}

_VOL_KEYS = (
    "volume", "vol",
    "tick_volume", "tickvol", "tickvolume", "tick_volume_", "tick_volume",
    "tick_volume", "tick_volume",
    "tick_volume", "tick_volume",
    "tick_volume",  # defensive
    "tick_volume",  # defensive
    "tick_volume",  # defensive
    "tick_volume",  # defensive
    "tick_volume",  # defensive
    "tick_volume",  # defensive
    "tick_volume",  # defensive
    "tick_volume",  # defensive
    "tick_volume",  # defensive
    "tick_volume",  # defensive
    "tick_volume",  # defensive
    "tick_volume",  # defensive
    "tick_volume",  # defensive
    "tick_volume",  # defensive
    "tick_volume",  # defensive
    "tick_volume",  # defensive
    "tick_volume",  # defensive
    "tick_volume",  # defensive
    "tick_volume",  # defensive
    "tick_volume",  # defensive
    "tick_volume",  # defensive
    "tick_volume",  # defensive
    "tick_volume",  # defensive
)

# Also accept MT5 canonical keys after normalization:
# <TICKVOL> -> tickvol
# <VOL> -> vol
# We'll explicitly search these too:
_VOL_ALT = ("tickvol", "vol", "tick_volume", "tick_volume", "tick_volume", "tick_volume", "tick_volume", "tick_volume")


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        s = str(x).strip()
        if s == "":
            return default
        return float(s)
    except Exception:
        return default


def _parse_time_best_effort(s: str) -> datetime:
    s = (s or "").strip()
    # ISO-like first
    try:
        return datetime.fromisoformat(s.replace("Z", ""))
    except Exception:
        pass

    fmts = [
        "%Y-%m-%d %H:%M:%S",
        "%Y.%m.%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y.%m.%d %H:%M",
        "%Y/%m/%d %H:%M",
        "%Y%m%d %H:%M:%S",
    ]
    for f in fmts:
        try:
            return datetime.strptime(s, f)
        except Exception:
            continue

    raise ValueError(f"Unparseable timestamp: {s!r}")


def _parse_date_time_pair(date_s: str, time_s: str) -> datetime:
    """
    MT5 often uses:
      DATE: 2026.01.29
      TIME: 22:07
    or DATE: 2026-01-29
    """
    ds = (date_s or "").strip()
    ts = (time_s or "").strip()

    # Common pairs
    fmts = [
        ("%Y.%m.%d", "%H:%M:%S"),
        ("%Y.%m.%d", "%H:%M"),
        ("%Y-%m-%d", "%H:%M:%S"),
        ("%Y-%m-%d", "%H:%M"),
        ("%Y/%m/%d", "%H:%M:%S"),
        ("%Y/%m/%d", "%H:%M"),
    ]
    for df, tf in fmts:
        try:
            d = datetime.strptime(ds, df)
            t = datetime.strptime(ts, tf)
            return d.replace(hour=t.hour, minute=t.minute, second=t.second, microsecond=0)
        except Exception:
            continue

    # Fallback: try joining then best-effort
    return _parse_time_best_effort(f"{ds} {ts}")


def _pick_key(row: Dict[str, str], candidates: Tuple[str, ...]) -> Optional[str]:
    for k in candidates:
        if k in row and row[k] not in (None, ""):
            return k
    return None


def _pick_ohlc_key(row: Dict[str, str], kind: str) -> Optional[str]:
    for k in _OHLC_KEYS[kind]:
        if k in row and row[k] not in (None, ""):
            return k
    return None


def _pick_volume_key(row: Dict[str, str]) -> Optional[str]:
    # Prefer tick volume if present
    for k in ("tick_volume", "tickvol", "tick_volume_", "tickvolume"):
        if k in row and row[k] not in (None, ""):
            return k
    for k in ("volume", "vol"):
        if k in row and row[k] not in (None, ""):
            return k
    return None


def load_1m_bars(csv_path: str, counters: Dict[str, Any]) -> List[Bar]:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    bars: List[Bar] = []

    with open(csv_path, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("CSV has no header row.")

        # Normalize headers
        norm_fieldnames = [_norm_key(fn) for fn in reader.fieldnames]
        reader.fieldnames = norm_fieldnames  # type: ignore

        for row in reader:
            try:
                # Normalize row keys too
                r = {_norm_key(k): (v if v is not None else "") for k, v in row.items()}

                # Timestamp logic:
                # Prefer single datetime field, else DATE+TIME pair.
                dt_key = _pick_key(r, _DATETIME_KEYS)
                date_key = _pick_key(r, _DATE_KEYS)
                time_key = _pick_key(r, _TIME_ONLY_KEYS)

                if dt_key and r.get(dt_key, "").strip():
                    ts = _parse_time_best_effort(r[dt_key])
                elif date_key and time_key and r.get(date_key, "").strip() and r.get(time_key, "").strip():
                    ts = _parse_date_time_pair(r[date_key], r[time_key])
                else:
                    # Some CSVs use "date" as a full datetime; try that
                    if "date" in r and r["date"].strip():
                        ts = _parse_time_best_effort(r["date"])
                    else:
                        counters["exceptions_count"] += 1
                        continue

                ok = _pick_ohlc_key(r, "open")
                hk = _pick_ohlc_key(r, "high")
                lk = _pick_ohlc_key(r, "low")
                ck = _pick_ohlc_key(r, "close")
                if not (ok and hk and lk and ck):
                    counters["exceptions_count"] += 1
                    continue

                vkey = _pick_volume_key(r)

                o = _safe_float(r.get(ok, ""))
                h = _safe_float(r.get(hk, ""))
                l = _safe_float(r.get(lk, ""))
                c = _safe_float(r.get(ck, ""))
                v = _safe_float(r.get(vkey, ""), 0.0) if vkey else 0.0

                # NaN guard
                if any(x != x for x in (o, h, l, c, v)):
                    counters["nan_or_inf_count"] += 1
                    continue

                bars.append(Bar(ts=ts, o=o, h=h, l=l, c=c, v=v))

            except Exception:
                counters["exceptions_count"] += 1
                continue

    bars.sort(key=lambda b: b.ts)
    counters["bars_1m_total"] = len(bars)
    return bars


# ----------------------------
# Build 5m bars from 1m
# ----------------------------

def floor_to_5m(ts: datetime) -> datetime:
    minute = (ts.minute // 5) * 5
    return ts.replace(minute=minute, second=0, microsecond=0)


def build_5m(bars_1m: List[Bar], counters: Dict[str, Any]) -> List[Bar]:
    if not bars_1m:
        counters["bars_5m_total"] = 0
        return []

    buckets: Dict[datetime, List[Bar]] = {}
    last_ts: Optional[datetime] = None

    for b in bars_1m:
        # Late-bar detection (monotonic time)
        if last_ts is not None and b.ts < last_ts:
            counters["late_bar_events"] += 1
        last_ts = b.ts

        k = floor_to_5m(b.ts)
        buckets.setdefault(k, []).append(b)

    bars_5m: List[Bar] = []
    for k in sorted(buckets.keys()):
        chunk = buckets[k]
        o = chunk[0].o
        c = chunk[-1].c
        h = max(x.h for x in chunk)
        l = min(x.l for x in chunk)
        v = sum(x.v for x in chunk)
        bars_5m.append(Bar(ts=k, o=o, h=h, l=l, c=c, v=v))

    counters["bars_5m_total"] = len(bars_5m)
    return bars_5m


# ----------------------------
# Regime gating (FX rules)
# ----------------------------

def regime_gate_allow(symbol: str, bars_5m: List[Bar], idx: int, min_5m_bars: int) -> bool:
    if idx + 1 < min_5m_bars:
        return False

    if FX_RULES_AVAILABLE:
        try:
            rules = FXRules()
            if hasattr(rules, "allow"):
                return bool(rules.allow(symbol=symbol, bars_5m=bars_5m, idx=idx))
            if hasattr(rules, "is_allowed"):
                return bool(rules.is_allowed(symbol=symbol, bars_5m=bars_5m, idx=idx))
        except Exception:
            # If rules fail, do not block analysis; fall back to allow once min bars reached
            return True

    return True


# ----------------------------
# Main replay loop
# ----------------------------

def run_replay(csv_path: str, symbol: str, min_5m_bars: int) -> Dict[str, Any]:
    counters: Dict[str, Any] = {
        "bars_1m_total": 0,
        "bars_5m_total": 0,
        "bars_5m_valid": 0,
        "regime_allow_count": 0,
        "regime_block_count": 0,
        "signals_generated_total": 0,
        "signals_suppressed_by_regime": 0,
        "exceptions_count": 0,
        "nan_or_inf_count": 0,
        "late_bar_events": 0,
        "fx_rules_available": bool(FX_RULES_AVAILABLE),
    }

    bars_1m = load_1m_bars(csv_path, counters)
    bars_5m = build_5m(bars_1m, counters)

    counters["bars_5m_valid"] = 1 if counters["bars_5m_total"] >= min_5m_bars else 0

    for i in range(len(bars_5m)):
        allow = regime_gate_allow(symbol=symbol, bars_5m=bars_5m, idx=i, min_5m_bars=min_5m_bars)
        if allow:
            counters["regime_allow_count"] += 1
        else:
            counters["regime_block_count"] += 1

    return counters


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="REA FX replay (v4) + fx_rules + counters [ANALYSIS-ONLY]")
    p.add_argument("--csv", required=True, help="Path to 1m CSV file")
    p.add_argument("--symbol", required=True, help="Symbol (e.g., EURUSD)")
    p.add_argument("--min5", type=int, default=40, help="Minimum 5m bars before allow (default 40)")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    csv_path = args.csv
    symbol = args.symbol
    min_5m_bars = int(args.min5)

    counters = run_replay(csv_path=csv_path, symbol=symbol, min_5m_bars=min_5m_bars)

    meta = {
        "mode": "replay_v4_fxrules_counters",
        "analysis_only": True,
        "symbol": symbol,
        "csv": csv_path,
        "min_5m_bars": min_5m_bars,
        "fx_rules_available": bool(counters.get("fx_rules_available", False)),
    }

    print_summary(counters=counters, meta=meta, include_raw=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())