"""
REA Capital — FX Pairs Replay (v4) + FX Rules + Counters  [ANALYSIS-ONLY]
=======================================================================

Task 6.6C: Use data adapters (auto-detect) so ANY acceptable source format
can be replayed into a canonical bar stream, then summarized via counters_summary.py.

Safety:
- ANALYSIS-ONLY. No MT5. No broker. No execution.

CSV:
- Supports multiple schemas via data_adapters.py (auto-detect by default).
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from counters_summary import print_summary
from data_adapters import Bar, load_bars_from_csv

# Optional FX rules module
FX_RULES_AVAILABLE = True
try:
    from regime.fx_rules import FXRules  # type: ignore
except Exception:
    FX_RULES_AVAILABLE = False


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
# Regime gating
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
            return True

    return True


# ----------------------------
# Main replay
# ----------------------------

def run_replay(csv_path: str, symbol: str, min_5m_bars: int, adapter: str) -> Dict[str, Any]:
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
        "adapter_used": "",
        "delimiter_used": "",
    }

    bars_1m, adapter_used, delim = load_bars_from_csv(
        csv_path=csv_path,
        counters=counters,
        adapter_name=adapter,
    )
    counters["adapter_used"] = adapter_used
    counters["delimiter_used"] = delim

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
    p = argparse.ArgumentParser(description="REA FX replay v4 + fx_rules + counters [ANALYSIS-ONLY]")
    p.add_argument("--csv", required=True, help="Path to CSV file")
    p.add_argument("--symbol", required=True, help="Symbol label (e.g., EURUSD)")
    p.add_argument("--min5", type=int, default=40, help="Minimum 5m bars before allow (default 40)")
    p.add_argument("--adapter", default="auto", help="Adapter: auto | std_ohlcv | mt5_csv | generic_ohlc")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    csv_path = args.csv
    symbol = args.symbol
    min_5m_bars = int(args.min5)
    adapter = args.adapter

    counters = run_replay(csv_path=csv_path, symbol=symbol, min_5m_bars=min_5m_bars, adapter=adapter)

    meta = {
        "mode": "replay_v4_fxrules_counters",
        "analysis_only": True,
        "symbol": symbol,
        "csv": csv_path,
        "min_5m_bars": min_5m_bars,
        "fx_rules_available": bool(counters.get("fx_rules_available", False)),
        "adapter_used": counters.get("adapter_used", ""),
        "delimiter_used": counters.get("delimiter_used", ""),
    }

    print_summary(counters=counters, meta=meta, include_raw=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())