"""
test_regime_gate_v3.py — REA Capital
RegimeGate expects bar objects with attributes like `c` (close).
This runner builds the expected shape and calls:
  RegimeGate.evaluate(bars_5m=..., as_of_utc=...)

Input:  sample_spy_5m.csv (ts_utc, close, volume)
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, List, Optional


def parse_ts(s: str) -> Optional[datetime]:
    s = (s or "").strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except Exception:
        return None


@dataclass
class GateBar:
    # Match RegimeGate's expected attribute names
    ts_utc: Any
    c: float          # close
    v: float = 1.0    # volume


def load_gate_bars(csv_path: str) -> List[GateBar]:
    bars: List[GateBar] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            ts_s = row.get("ts_utc") or row.get("timestamp")
            close_s = row.get("close") or row.get("c")
            vol_s = row.get("volume") or row.get("v")

            if not ts_s or not close_s:
                continue

            ts = parse_ts(ts_s)
            ts_val: Any = ts if ts is not None else ts_s

            c = float(close_s)
            v = float(vol_s) if vol_s else 1.0

            bars.append(GateBar(ts_utc=ts_val, c=c, v=v))
    return bars


def infer_allow(result: Any):
    """
    Try to infer allow/deny from common result shapes.
    """
    allow = None
    reason = None

    # bool
    if isinstance(result, bool):
        return result, None

    # dict
    if isinstance(result, dict):
        if "allow" in result:
            allow = bool(result.get("allow"))
        reason = result.get("reason") or result.get("block_reason") or result.get("reasons")
        return allow, reason

    # object with attrs
    for attr in ("allow", "decision"):
        if hasattr(result, attr):
            val = getattr(result, attr)
            # decision can be enum-like: "ALLOW"/"BLOCK"
            if attr == "allow":
                allow = bool(val)
            elif attr == "decision":
                allow = str(val).upper().endswith("ALLOW")

    for attr in ("reason", "block_reason", "reasons"):
        if hasattr(result, attr):
            reason = getattr(result, attr)

    return allow, reason


def main() -> int:
    try:
        from regime.gate import RegimeGate  # type: ignore
    except Exception as e:
        print("FAILED to import RegimeGate:", repr(e))
        return 2

    csv_path = "sample_spy_5m.csv"
    if not os.path.exists(csv_path):
        print("Missing sample_spy_5m.csv")
        return 3

    bars_5m = load_gate_bars(csv_path)
    if len(bars_5m) < 1:
        print("No usable 5m bars loaded.")
        return 4

    as_of = bars_5m[-1].ts_utc
    if not isinstance(as_of, datetime):
        as_of = datetime.now(timezone.utc)

    print("=" * 70)
    print("REA — RegimeGate Proper Invocation (V3: expects bar.c)")
    print("Bars supplied:", len(bars_5m))
    print("As-of UTC:", as_of)
    print("=" * 70)

    gate = RegimeGate()

    try:
        result = gate.evaluate(bars_5m=bars_5m, as_of_utc=as_of)
    except Exception as e:
        print("RegimeGate.evaluate FAILED:", repr(e))
        return 5

    print("\n[Raw Result]")
    print(result)

    allow, reason = infer_allow(result)

    print("\n[Decision]")
    print("ALLOW:", allow)
    if reason is not None:
        print("Reason(s):", reason)

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())