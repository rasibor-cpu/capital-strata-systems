"""
test_regime_gate_v2.py — REA Capital
Properly invoke RegimeGate.evaluate(bars_5m, as_of_utc) using bar OBJECTS
(not dicts), because the gate expects attributes like bar.close, bar.ts_utc.

Input:  sample_spy_5m.csv (ts_utc, close, volume)
Output: prints raw decision + inferred allow/reason when possible
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional, Any


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
class Bar5m:
    ts_utc: Any
    close: float
    volume: float = 1.0


def load_5m_bars(csv_path: str) -> List[Bar5m]:
    bars: List[Bar5m] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            ts_s = row.get("ts_utc") or row.get("timestamp")
            close_s = row.get("close") or row.get("c")
            vol_s = row.get("volume") or row.get("v")

            if not ts_s or not close_s:
                continue

            ts = parse_ts(ts_s) or ts_s
            close = float(close_s)
            vol = float(vol_s) if vol_s else 1.0

            bars.append(Bar5m(ts_utc=ts, close=close, volume=vol))
    return bars


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

    bars_5m = load_5m_bars(csv_path)
    if len(bars_5m) < 1:
        print("No usable 5m bars loaded.")
        return 4

    as_of = bars_5m[-1].ts_utc
    if isinstance(as_of, str):
        as_of = datetime.now(timezone.utc)

    print("=" * 70)
    print("REA — RegimeGate Proper Invocation (V2: object bars)")
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

    # Try to infer allow/reason across common shapes
    allow = None
    reason = None

    if isinstance(result, bool):
        allow = result

    # dataclass-like / namedtuple-like
    for attr in ("allow", "decision", "reasons", "reason", "block_reason"):
        if hasattr(result, attr):
            v = getattr(result, attr)
            if attr == "allow":
                allow = bool(v)
            if attr in ("reason", "block_reason"):
                reason = v
            if attr == "reasons" and v:
                reason = v

    # dict shape
    if isinstance(result, dict):
        if "allow" in result:
            allow = bool(result.get("allow"))
        reason = result.get("reason") or result.get("block_reason") or result.get("reasons")

    print("\n[Decision]")
    print("ALLOW:", allow)
    if reason is not None:
        print("Reason(s):", reason)

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())