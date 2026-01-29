"""
REA Capital — FX Replay v5 (Signals-Only, Analysis-Only)
=======================================================

Task 9.1:
- Load 1m bars via data_adapters (auto-detect)
- Build 5m bars
- Apply regime gate (min 5m bars + optional fx_rules if present)
- Run multiple signal models (VWAP MR + Breakout)
- Count:
    signals_generated_total (only when regime allows)
    signals_suppressed_by_regime (signals that would have existed during BLOCK)
- Print canonical counters summary
- NO EXECUTION. NO MT5. NO BROKER. NO ORDERS.

Run example:
python run_fx_pairs_replay_v5_signals_only.py --csv "C:\\Users\\rasib\\source\\REA-capital-trading-engine\\data_fx\\EUR_USD_1m.csv" --symbol EURUSD --adapter auto
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

# Optional FX rules module (if present)
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
    return name.replace("_", "").replace("-", "").upper() if name else "UNKNOWN"


def bars_to_dicts(bars: List[Bar]) -> List[Dict[str, Any]]:
    return [{"ts": b.ts, "o": b.o, "h": b.h, "l": b.l, "c": b.c, "v": b.v} for b in bars]


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
# Regime gate
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
            # analysis-only: do not hard-fail if rules throw
            return True

    return True


# ----------------------------
# Signal counting
# ----------------------------

def count_signals_for_index(
    bars_5m: List[Bar],
    idx: int,
    allowed: bool,
    counters: Dict[str, Any],
    vwap_lookback: int,
    vwap_z: float,
    brk_lookback: int,
    brk_buffer: float,
) -> None:
    # window up to idx inclusive
    window = bars_to_dicts(bars_5m[: idx + 1])

    total_new = 0
    total_new += len(generate_vwap_mean_reversion_signals(window, lookback=vwap_lookback, z_threshold=vwap_z))
    total_new += len(generate_breakout_signals(window, lookback=brk_lookback, buffer_pct=brk_buffer))

    if allowed:
        counters["signals_generated_total"] += total_new
    else:
        counters["signals_suppressed_by_regime"] += total_new


# ----------------------------
# Replay
# ----------------------------

def run_replay(csv_path: str, symbol: str, min_5m_bars: int, adapter: str,
              vwap_lookback: int, vwap_z: float, brk_lookback: int, brk_buffer: float) -> Dict[str, Any]:

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

    bars_1m, adapter_used, delim = load_bars_from_csv(csv_path, counters, adapter_name=adapter)
    counters["adapter_used"] = adapter_used
    counters["delimiter_used"] = delim
    counters["bars_1m_total"] = len(bars_1m)

    bars_5m = build_5m(bars_1m, counters)
    counters["bars_5m_valid"] = 1 if counters["bars_5m_total"] >= min_5m_bars else 0

    for i in range(len(bars_5m)):
        allowed = regime_gate_allow(symbol, bars_5m, i, min_5m_bars)
        if allowed:
            counters["regime_allow_count"] += 1
        else:
            counters["regime_block_count"] += 1

        count_signals_for_index(
            bars_5m=bars_5m,
            idx=i,
            allowed=allowed,
            counters=counters,
            vwap_lookback=vwap_lookback,
            vwap_z=vwap_z,
            brk_lookback=brk_lookback,
            brk_buffer=brk_buffer,
        )

    return counters


# ----------------------------
# CLI
# ----------------------------

def main() -> int:
    p = argparse.ArgumentParser(description="REA FX Replay v5 (signals-only, analysis-only)")
    p.add_argument("--csv", required=True)
    p.add_argument("--symbol", default="")
    p.add_argument("--min5", type=int, default=40)
    p.add_argument("--adapter", default="auto")

    # signal params
    p.add_argument("--vwap_lookback", type=int, default=20)
    p.add_argument("--vwap_z", type=float, default=1.5)
    p.add_argument("--brk_lookback", type=int, default=10)
    p.add_argument("--brk_buffer", type=float, default=0.05)

    args = p.parse_args()

    csv_path = os.path.normpath(args.csv)
    if not os.path.exists(csv_path):
        print(f"CSV not found: {csv_path}")
        return 2

    symbol = (args.symbol or "").strip().upper() or _infer_symbol_from_path(csv_path)

    counters = run_replay(
        csv_path=csv_path,
        symbol=symbol,
        min_5m_bars=int(args.min5),
        adapter=str(args.adapter),
        vwap_lookback=int(args.vwap_lookback),
        vwap_z=float(args.vwap_z),
        brk_lookback=int(args.brk_lookback),
        brk_buffer=float(args.brk_buffer),
    )

    meta = {
        "mode": "replay_v5_signals_only",
        "analysis_only": True,
        "symbol": symbol,
        "csv": csv_path,
        "min_5m_bars": int(args.min5),
        "adapter_used": counters.get("adapter_used", ""),
        "delimiter_used": counters.get("delimiter_used", ""),
        "fx_rules_available": bool(counters.get("fx_rules_available", False)),
        "vwap_lookback": int(args.vwap_lookback),
        "vwap_z": float(args.vwap_z),
        "brk_lookback": int(args.brk_lookback),
        "brk_buffer": float(args.brk_buffer),
    }

    print_summary(counters=counters, meta=meta, include_raw=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())