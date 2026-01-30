"""
test_vwap_live_dryrun.py | REA Capital
Purpose:
- Live-data (CSV) dry-run: RegimeGate + VWAP signal generation
- LOG-ONLY (no execution, no orders)
- Confirms end-to-end: load bars -> regime allow -> signal(s)

Design:
- VWAP signal expects dict bars: ts,h,l,c,v
- RegimeGate expects attribute-style bars: bar.c, bar.h, bar.l, bar.v, bar.ts_utc
So we load ONCE, then generate:
  (A) bars_dict  for VWAP
  (B) bars_attr  for RegimeGate
"""

from __future__ import annotations

import csv
import os
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

from regime.gate import RegimeGate  # type: ignore
from signals.vwap_mean_reversion import generate_vwap_mean_reversion_signals


def parse_ts(v: str) -> Optional[datetime]:
    try:
        if not v:
            return None
        if v.endswith("Z"):
            v = v[:-1] + "+00:00"
        dt = datetime.fromisoformat(v)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt
    except Exception:
        return None


def load_5m_bars_dual(csv_path: str) -> Tuple[List[Dict[str, Any]], List[Any]]:
    """
    Load 5m bars once, output both:
      - bars_dict (for VWAP): {"ts","h","l","c","v"}
      - bars_attr (for RegimeGate): bar.ts_utc, bar.h, bar.l, bar.c, bar.v
    Accepts common CSV headers:
      ts/ts_utc/timestamp, high/low/close (or h/l/c), volume (or v)
    """
    bars_dict: List[Dict[str, Any]] = []
    bars_attr: List[Any] = []

    with open(csv_path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            ts_raw = row.get("ts") or row.get("ts_utc") or row.get("timestamp")
            c_raw = row.get("c") or row.get("close")
            h_raw = row.get("h") or row.get("high") or c_raw
            l_raw = row.get("l") or row.get("low") or c_raw
            v_raw = row.get("v") or row.get("volume") or 1.0

            ts = parse_ts(ts_raw) if ts_raw else None
            if ts is None or c_raw is None:
                continue

            try:
                c = float(c_raw)
                h = float(h_raw)
                l = float(l_raw)
                v = float(v_raw) if v_raw is not None else 1.0
            except Exception:
                continue

            d = {"ts": ts, "h": h, "l": l, "c": c, "v": v}
            bars_dict.append(d)

            a = SimpleNamespace(
                ts_utc=ts,
                h=h,
                l=l,
                c=c,
                v=v,
                # harmless aliases
                close=c,
                volume=v,
            )
            bars_attr.append(a)

    return bars_dict, bars_attr


def _decision_to_allow(decision: Any) -> Optional[bool]:
    if decision is None:
        return None
    name = getattr(decision, "name", None)
    value = getattr(decision, "value", None)
    cand = name or value or decision
    try:
        s = str(cand).strip().upper()
    except Exception:
        return None
    if "BLOCK" in s:
        return False
    if "ALLOW" in s:
        return True
    return None


def main() -> int:
    csv_path = "sample_spy_5m.csv"
    if not os.path.exists(csv_path):
        print("Missing sample_spy_5m.csv")
        print("Put a 5-minute CSV in project root named sample_spy_5m.csv and rerun.")
        return 2

    bars_dict, bars_attr = load_5m_bars_dual(csv_path)
    if len(bars_dict) < 20 or len(bars_attr) < 20:
        print("Not enough usable bars loaded:", len(bars_dict))
        print("Need at least 20 for lookback.")
        return 3

    as_of = bars_dict[-1]["ts"]

    print("=" * 70)
    print("REA – Live Dry Run (CSV) — RegimeGate + VWAP (LOG ONLY)")
    print("Bars loaded:", len(bars_dict))
    print("As-of UTC:", as_of)
    print("=" * 70)

    # 1) Regime gate check (attribute-style bars)
    gate = RegimeGate()
    try:
        rg = gate.evaluate(bars_5m=bars_attr, as_of_utc=as_of)  # type: ignore
    except Exception as e:
        print("RegimeGate.evaluate FAILED:", repr(e))
        return 4

    print("\n[RegimeGate Raw]")
    print(rg)

    allow = None
    reason = None

    if isinstance(rg, bool):
        allow = rg
    elif isinstance(rg, dict):
        allow = bool(rg.get("allow"))
        reason = rg.get("reason") or rg.get("block_reason")
    elif hasattr(rg, "decision"):
        allow = _decision_to_allow(getattr(rg, "decision", None))
        if hasattr(rg, "reasons"):
            rs = getattr(rg, "reasons", None)
            if isinstance(rs, list) and rs:
                reason = "; ".join(str(x) for x in rs)

    print("\n[RegimeGate Decision]")
    print("ALLOW:", allow)
    if reason:
        print("Reason:", reason)

    # 2) VWAP signals (dict bars)
    print("\n[VWAP Signals]")
    signals = generate_vwap_mean_reversion_signals(
        bars_5m=bars_dict,
        lookback=20,
        z_threshold=1.5,
    )

    if not signals:
        print("No VWAP signals generated (expected sometimes).")
    else:
        for s in signals[-5:]:
            print(s)

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
