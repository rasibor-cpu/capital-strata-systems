"""
REA Capital — FX Replay v4 + FX Rules + Signals + Execution Router (DRY-RUN)
===========================================================================

Task 8.2:
- Builds 1m → 5m bars
- Applies regime gate
- Runs multiple signal models
- Routes signals through DRY-RUN execution router
- Tracks execution decisions (allowed vs blocked)
- NO EXECUTION, NO MT5, NO BROKER
"""

from __future__ import annotations

import argparse
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from counters_summary import print_summary
from data_adapters import Bar, load_bars_from_csv
from signals.vwap_mean_reversion import generate_vwap_mean_reversion_signals
from signals.breakout_momentum import generate_breakout_signals
from engine.execution_router import ExecutionRouter

# Optional FX rules module
FX_RULES_AVAILABLE = True
try:
    from regime.fx_rules import FXRules  # type: ignore
except Exception:
    FX_RULES_AVAILABLE = False


# ----------------------------
# Utilities
# ----------------------------

def _infer_symbol_from_path(path: str) -> str:
    base = os.path.basename(path)
    name = os.path.splitext(base)[0]
    name = re.sub(r"(_\d+[mhdw])$", "", name, flags=re.IGNORECASE)
    return name.replace("_", "").upper() if name else "UNKNOWN"


def bars_to_dicts(bars: List[Bar]) -> List[Dict[str, Any]]:
    return [{"ts": b.ts, "o": b.o, "h": b.h, "l": b.l, "c": b.c, "v": b.v} for b in bars]


# ----------------------------
# Build 5m bars
# ----------------------------

def floor_to_5m(ts: datetime) -> datetime:
    return ts.replace(minute=(ts.minute // 5) * 5, second=0, microsecond=0)


def build_5m(bars_1m: List[Bar], counters: Dict[str, Any]) -> List[Bar]:
    buckets: Dict[datetime, List[Bar]] = {}
    last_ts: Optional[datetime] = None

    for b in bars_1m:
        if last_ts and b.ts < last_ts:
            counters["late_bar_events"] += 1
        last_ts = b.ts

        k = floor_to_5m(b.ts)
        buckets.setdefault(k, []).append(b)

    bars_5m: List[Bar] = []
    for k in sorted(buckets):
        chunk = buckets[k]
        bars_5m.append(
            Bar(
                ts=k,
                o=chunk[0].o,
                h=max(x.h for x in chunk),
                l=min(x.l for x in chunk),
                c=chunk[-1].c,
                v=sum(x.v for x in chunk),
            )
        )

    counters["bars_5m_total"] = len(bars_5m)
    return bars_5m


# ----------------------------
# Regime Gate
# ----------------------------

def regime_allowed(symbol: str, bars_5m: List[Bar], idx: int, min_5m: int) -> bool:
    if idx + 1 < min_5m:
        return False

    if FX_RULES_AVAILABLE:
        try:
            rules = FXRules()
            if hasattr(rules, "allow"):
                return bool(rules.allow(symbol=symbol, bars_5m=bars_5m, idx=idx))
        except Exception:
            return True

    return True


# ----------------------------
# Replay
# ----------------------------

def run_replay(csv: str, symbol: str, min_5m: int, adapter: str) -> Dict[str, Any]:
    counters: Dict[str, Any] = {
        "bars_1m_total": 0,
        "bars_5m_total": 0,
        "regime_allow_count": 0,
        "regime_block_count": 0,
        "signals_generated_total": 0,
        "signals_suppressed_by_regime": 0,
        "execution_decisions_total": 0,
        "execution_allowed": 0,
        "execution_blocked": 0,
        "late_bar_events": 0,
        "exceptions_count": 0,
        "adapter_used": "",
        "delimiter_used": "",
        "fx_rules_available": FX_RULES_AVAILABLE,
    }

    bars_1m, adapter_used, delim = load_bars_from_csv(csv, counters, adapter)
    counters["adapter_used"] = adapter_used
    counters["delimiter_used"] = delim
    counters["bars_1m_total"] = len(bars_1m)

    bars_5m = build_5m(bars_1m, counters)

    router = ExecutionRouter(analysis_only=True)

    for i, bar in enumerate(bars_5m):
        allowed = regime_allowed(symbol, bars_5m, i, min_5m)

        if allowed:
            counters["regime_allow_count"] += 1
        else:
            counters["regime_block_count"] += 1

        window = bars_to_dicts(bars_5m[: i + 1])

        signals = []
        signals += generate_vwap_mean_reversion_signals(window)
        signals += generate_breakout_signals(window)

        if allowed:
            counters["signals_generated_total"] += len(signals)
        else:
            counters["signals_suppressed_by_regime"] += len(signals)

        for sig in signals:
            decision = router.route_signal(
                symbol=symbol,
                signal=sig,
                regime_allowed=allowed,
            )
            counters["execution_decisions_total"] += 1
            if decision.allowed:
                counters["execution_allowed"] += 1
            else:
                counters["execution_blocked"] += 1

    return counters


# ----------------------------
# CLI
# ----------------------------

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--csv", required=True)
    p.add_argument("--symbol", default="")
    p.add_argument("--min5", type=int, default=40)
    p.add_argument("--adapter", default="auto")
    args = p.parse_args()

    csv = os.path.normpath(args.csv)
    if not os.path.exists(csv):
        print(f"CSV not found: {csv}")
        return 2

    symbol = args.symbol or _infer_symbol_from_path(csv)

    counters = run_replay(csv, symbol, args.min5, args.adapter)

    meta = {
        "mode": "replay_v4_fxrules_signals_execution_dryrun",
        "analysis_only": True,
        "symbol": symbol,
        "csv": csv,
    }

    print_summary(counters=counters, meta=meta, include_raw=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())