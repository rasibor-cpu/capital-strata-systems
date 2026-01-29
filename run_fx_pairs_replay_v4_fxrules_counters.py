"""
REA Capital — FX Replay v4 + FX Rules + Counters + Multi-Signals (ANALYSIS-ONLY)
=============================================================================

Task 7.5: Wire multiple signal generators behind the regime gate, still analysis-only.
- Uses data_adapters.py (auto-detect CSV formats)
- Builds 5m bars from 1m
- Applies regime gate
- Runs TWO signal models:
    1) VWAP mean reversion
    2) Breakout momentum
- Counts signals generated vs suppressed-by-regime
- Prints canonical counters summary via counters_summary.py

NO EXECUTION. NO MT5. NO BROKER.
"""

from __future__ import annotations

import argparse
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from counters_summary import print_summary
from data_adapters import Bar, load_bars_from_csv
from signals.vwap_mean_reversion import generate_vwap_mean_reversion_signals
from signals.breakout_momentum import generate_breakout_signals

# Optional FX rules module (safe import)
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
    name = name.replace("_", "").replace("-", "").replace(" ", "")
    return name.upper() if name else "UNKNOWN"


def _list_csvs_under(folder: str) -> List[str]:
    out: List[str] = []
    if not os.path.isdir(folder):
        return out
    for root, _, files in os.walk(folder):
        for fn in files:
            if fn.lower().endswith(".csv"):
                out.append(os.path.join(root, fn))
    return out


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
# Signal generation (analysis-only)
# ----------------------------

def count_signals(
    bars_5m: List[Bar],
    idx: int,
    allowed: bool,
    counters: Dict[str, Any],
    # VWAP params
    vwap_lookback: int,
    vwap_z: float,
    # Breakout params
    brk_lookback: int,
    brk_buffer_pct: float,
) -> None:
    """
    Runs both models on a window ending at idx and updates counters.
    If regime BLOCK: signals are counted as suppressed.
    """
    # Build the window up to idx (inclusive)
    window = bars_5m[: idx + 1]
    window_dicts = bars_to_dicts(window)

    total_new = 0

    # Model 1: VWAP mean reversion (runs on tail window internally)
    sigs1 = generate_vwap_mean_reversion_signals(
        bars_5m=window_dicts,
        lookback=vwap_lookback,
        z_threshold=vwap_z,
    )
    total_new += len(sigs1)

    # Model 2: Breakout momentum
    sigs2 = generate_breakout_signals(
        bars_5m=window_dicts,
        lookback=brk_lookback,
        buffer_pct=brk_buffer_pct,
    )
    total_new += len(sigs2)

    if allowed:
        counters["signals_generated_total"] += total_new
    else:
        counters["signals_suppressed_by_regime"] += total_new


# ----------------------------
# Replay
# ----------------------------

def run_replay(
    csv_path: str,
    symbol: str,
    min_5m_bars: int,
    adapter: str,
    vwap_lookback: int,
    vwap_z: float,
    brk_lookback: int,
    brk_buffer_pct: float,
) -> Dict[str, Any]:
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
        allowed = regime_gate_allow(symbol=symbol, bars_5m=bars_5m, idx=i, min_5m_bars=min_5m_bars)
        if allowed:
            counters["regime_allow_count"] += 1
        else:
            counters["regime_block_count"] += 1

        count_signals(
            bars_5m=bars_5m,
            idx=i,
            allowed=allowed,
            counters=counters,
            vwap_lookback=vwap_lookback,
            vwap_z=vwap_z,
            brk_lookback=brk_lookback,
            brk_buffer_pct=brk_buffer_pct,
        )

    return counters


# ----------------------------
# CLI
# ----------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="REA FX replay v4 + fx_rules + counters + multi-signals [ANALYSIS-ONLY]",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    p.add_argument("csv_pos", nargs="?", help="CSV path (optional positional). If provided, overrides --csv.")
    p.add_argument("--csv", dest="csv_opt", help="CSV path (preferred).")

    p.add_argument("--symbol", default="", help="Symbol label (e.g., EURUSD). If omitted, inferred from filename.")
    p.add_argument("--min5", type=int, default=40, help="Minimum 5m bars before allow (default 40).")
    p.add_argument("--adapter", default="auto", help="Adapter: auto | std_ohlcv | mt5_csv | generic_ohlc")

    # VWAP params
    p.add_argument("--vwap_lookback", type=int, default=20, help="VWAP lookback on 5m bars (default 20).")
    p.add_argument("--vwap_z", type=float, default=1.5, help="VWAP deviation threshold (percent proxy) (default 1.5).")

    # Breakout params
    p.add_argument("--brk_lookback", type=int, default=10, help="Breakout lookback (default 10).")
    p.add_argument("--brk_buffer", type=float, default=0.05, help="Breakout buffer percent (default 0.05).")

    return p.parse_args()


def main() -> int:
    args = parse_args()

    csv_path = (args.csv_pos or args.csv_opt or "").strip()
    if not csv_path:
        print("ERROR: No CSV path provided.\n")
        print("Try:\n  python run_fx_pairs_replay_v4_fxrules_counters.py --csv \"data_fx\\EUR_USD_1m.csv\" --symbol EURUSD --adapter auto\n")
        return 2

    csv_path = os.path.normpath(csv_path)

    if not os.path.exists(csv_path):
        print(f"ERROR: CSV not found: {csv_path}\n")
        candidates = _list_csvs_under("data_fx")
        if candidates:
            print("Found these CSVs under ./data_fx:")
            for c in candidates:
                print(f"  {c}")
        else:
            print("No CSVs found under ./data_fx.")
        return 2

    symbol = (args.symbol or "").strip().upper()
    if not symbol:
        symbol = _infer_symbol_from_path(csv_path)

    counters = run_replay(
        csv_path=csv_path,
        symbol=symbol,
        min_5m_bars=int(args.min5),
        adapter=str(args.adapter or "auto"),
        vwap_lookback=int(args.vwap_lookback),
        vwap_z=float(args.vwap_z),
        brk_lookback=int(args.brk_lookback),
        brk_buffer_pct=float(args.brk_buffer),
    )

    meta = {
        "mode": "replay_v4_fxrules_counters_multi_signals",
        "analysis_only": True,
        "symbol": symbol,
        "csv": csv_path,
        "min_5m_bars": int(args.min5),
        "fx_rules_available": bool(counters.get("fx_rules_available", False)),
        "adapter_used": counters.get("adapter_used", ""),
        "delimiter_used": counters.get("delimiter_used", ""),
        "vwap_lookback": int(args.vwap_lookback),
        "vwap_z": float(args.vwap_z),
        "brk_lookback": int(args.brk_lookback),
        "brk_buffer": float(args.brk_buffer),
    }

    print_summary(counters=counters, meta=meta, include_raw=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())