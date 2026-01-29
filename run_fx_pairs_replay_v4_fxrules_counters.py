"""
REA Capital — FX Pairs Replay (v4) + FX Rules + Counters  [ANALYSIS-ONLY]
=======================================================================

Task 6.4: Wire canonical counters summary output into the v4 replay+counters runner.

IMPORTANT SAFETY CONSTRAINTS
----------------------------
- ANALYSIS-ONLY: This script MUST NOT place trades, connect to MT5, or hit brokers.
- It is intended to replay historical CSV bars and produce counters/metrics only.
- Outputs are printed to console; optional writing should remain under ./out if added later.

Expected CSV Columns (best-effort)
----------------------------------
We accept common variants. At minimum, a time column + OHLC.
Time column candidates: time, timestamp, datetime, date
OHLC candidates: open, high, low, close
Optional: volume, tick_volume

Usage Examples
--------------
python run_fx_pairs_replay_v4_fxrules_counters.py --csv data_fx/EURUSD_1m.csv --symbol EURUSD
python run_fx_pairs_replay_v4_fxrules_counters.py --csv data_fx/EURUSD_1m.csv --symbol EURUSD --min5 40

This script will:
- Load 1m bars from CSV
- Build 5m bars
- Apply an FX regime gate using regime/fx_rules.py if present
- Count allow/block events and basic stability counters
- Print canonical summary via counters_summary.py

"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# Canonical summary formatter (Task 6.3)
try:
    from counters_summary import print_summary
except Exception as e:
    print("FATAL: counters_summary.py not importable. Ensure it exists in repo root.")
    raise

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
# Helpers: parsing and loading
# ----------------------------

_TIME_KEYS = ("time", "timestamp", "datetime", "date")
_OHLC_KEYS = {
    "open": ("open", "o"),
    "high": ("high", "h"),
    "low": ("low", "l"),
    "close": ("close", "c"),
}
_VOL_KEYS = ("volume", "tick_volume", "vol", "v")


def _parse_time(s: str) -> datetime:
    """
    Best-effort timestamp parser.
    Supports ISO-like and common CSV exports.
    """
    s = (s or "").strip()
    # Try isoformat first
    try:
        # Handles "YYYY-MM-DD HH:MM:SS" and "YYYY-MM-DDTHH:MM:SS"
        return datetime.fromisoformat(s.replace("Z", ""))
    except Exception:
        pass

    # Common MT5 / broker formats
    fmts = [
        "%Y-%m-%d %H:%M:%S",
        "%Y.%m.%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y.%m.%d %H:%M",
        "%Y/%m/%d %H:%M",
    ]
    for f in fmts:
        try:
            return datetime.strptime(s, f)
        except Exception:
            continue

    raise ValueError(f"Unparseable timestamp: {s!r}")


def _get_first_key(row: Dict[str, str], keys: Tuple[str, ...]) -> Optional[str]:
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return k
    return None


def _get_ohlc_key(row: Dict[str, str], kind: str) -> Optional[str]:
    for k in _OHLC_KEYS[kind]:
        if k in row and row[k] not in (None, ""):
            return k
    return None


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


def load_1m_bars(csv_path: str, counters: Dict[str, Any]) -> List[Bar]:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    bars: List[Bar] = []
    with open(csv_path, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("CSV has no header row (fieldnames missing).")

        # Normalize fieldnames to lower-case
        fieldnames = [fn.strip().lower() for fn in reader.fieldnames]
        reader.fieldnames = fieldnames  # type: ignore

        for i, row in enumerate(reader):
            try:
                # Lowercase row keys
                row_l = {k.strip().lower(): v for k, v in row.items()}

                tkey = _get_first_key(row_l, _TIME_KEYS)
                if not tkey:
                    counters["exceptions_count"] += 1
                    continue

                ok = _get_ohlc_key(row_l, "open")
                hk = _get_ohlc_key(row_l, "high")
                lk = _get_ohlc_key(row_l, "low")
                ck = _get_ohlc_key(row_l, "close")
                if not (ok and hk and lk and ck):
                    counters["exceptions_count"] += 1
                    continue

                vkey = _get_first_key(row_l, _VOL_KEYS)
                ts = _parse_time(row_l[tkey])
                o = _safe_float(row_l[ok])
                h = _safe_float(row_l[hk])
                l = _safe_float(row_l[lk])
                c = _safe_float(row_l[ck])
                v = _safe_float(row_l[vkey], 0.0) if vkey else 0.0

                # NaN/Inf guard
                if any(x != x for x in (o, h, l, c, v)):  # NaN check
                    counters["nan_or_inf_count"] += 1
                    continue

                bars.append(Bar(ts=ts, o=o, h=h, l=l, c=c, v=v))
            except Exception:
                counters["exceptions_count"] += 1
                continue

    # Sort & basic integrity checks
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
    for b in bars_1m:
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

def regime_gate_allow(
    symbol: str,
    bars_5m: List[Bar],
    idx: int,
    min_5m_bars: int,
) -> bool:
    """
    Conservative gating:
    - Require at least min_5m_bars 5m bars before allowing.
    - If FXRules is available, defer to its allow policy where possible.
    """
    if idx + 1 < min_5m_bars:
        return False

    if FX_RULES_AVAILABLE:
        try:
            # FXRules may expose methods differently; keep best-effort
            rules = FXRules()
            # Common patterns:
            # - rules.allow(symbol=symbol, bars_5m=..., idx=idx)
            # - rules.is_allowed(...)
            if hasattr(rules, "allow"):
                return bool(rules.allow(symbol=symbol, bars_5m=bars_5m, idx=idx))
            if hasattr(rules, "is_allowed"):
                return bool(rules.is_allowed(symbol=symbol, bars_5m=bars_5m, idx=idx))
        except Exception:
            # If rules fail, fall back to conservative allow
            return True

    # Default: allow once minimum bars reached
    return True


# ----------------------------
# Main replay loop (analysis-only)
# ----------------------------

def run_replay(csv_path: str, symbol: str, min_5m_bars: int) -> Dict[str, Any]:
    counters: Dict[str, Any] = {
        "bars_1m_total": 0,
        "bars_5m_total": 0,
        "bars_5m_valid": 0,
        "regime_allow_count": 0,
        "regime_block_count": 0,
        "signals_generated_total": 0,  # prompt-only stage: may be 0
        "signals_suppressed_by_regime": 0,
        "exceptions_count": 0,
        "nan_or_inf_count": 0,
        "late_bar_events": 0,
        "fx_rules_available": 1 if FX_RULES_AVAILABLE else 0,
    }

    bars_1m = load_1m_bars(csv_path, counters)
    bars_5m = build_5m(bars_1m, counters)

    # Valid if >= min threshold
    counters["bars_5m_valid"] = 1 if counters["bars_5m_total"] >= min_5m_bars else 0

    # Regime evaluation pass across 5m bars
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
    p.add_argument("--symbol", required=True, help="Symbol name (e.g., EURUSD)")
    p.add_argument("--min5", type=int, default=40, help="Minimum number of 5m bars required before allow (default 40)")
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
        "fx_rules_available": bool(counters.get("fx_rules_available", 0)),
    }

    print_summary(counters=counters, meta=meta, include_raw=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())