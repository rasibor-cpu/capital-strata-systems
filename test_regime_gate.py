"""
test_regime_gate.py | REA Capital
Purpose:
- Properly invoke RegimeGate.evaluate(bars_5m, as_of_utc)
- Determine TRUE allow/block state
- Explain why VWAP prompts are currently blocked
- NO engine edits, NO execution
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, List, Optional

import csv
import os


def parse_ts(v: str) -> Optional[datetime]:
    """
    Parse timestamps from CSV. Supports:
    - ISO strings with 'Z' suffix (converted to +00:00)
    - ISO strings with timezone offset
    Returns aware datetime in UTC, or None.
    """
    try:
        if not v:
            return None
        if v.endswith("Z"):
            v = v[:-1] + "+00:00"
        dt = datetime.fromisoformat(v)
        # Ensure timezone-aware in UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt
    except Exception:
        return None


def load_5m_bars(csv_path: str) -> List[Any]:
    """
    Load 5-minute bars from a CSV into objects with attribute-style access:
      bar.ts_utc, bar.o, bar.h, bar.l, bar.c, bar.v

    This matches RegimeGate implementations that expect bar.c (not dict keys).
    If your CSV only has close + volume, we safely map:
      o=h=l=c=close, v=volume (or 1.0 fallback)
    """
    bars: List[Any] = []

    with open(csv_path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            ts = row.get("ts_utc") or row.get("timestamp")
            close = row.get("close") or row.get("c")
            if not ts or close is None:
                continue

            ts_dt = parse_ts(ts)
            if ts_dt is None:
                continue

            try:
                c = float(close)
            except Exception:
                continue

            # Volume is optional
            v_raw = row.get("volume") or row.get("v") or 1.0
            try:
                v = float(v_raw) if v_raw is not None else 1.0
            except Exception:
                v = 1.0

            # Build an attribute-style bar object
            bar = SimpleNamespace(
                ts_utc=ts_dt,
                o=c,
                h=c,
                l=c,
                c=c,
                v=v,
                close=c,      # keep friendly aliases (harmless)
                volume=v,
            )
            bars.append(bar)

    return bars


def main() -> int:
    try:
        from regime.gate import RegimeGate  # type: ignore
    except Exception as e:
        print("FAILED to import RegimeGate:", repr(e))
        return 2

    gate = RegimeGate()

    csv_path = "sample_spy_5m.csv"
    if not os.path.exists(csv_path):
        print("Missing sample_spy_5m.csv")
        print("Provide a 5-minute bar file and rerun")
        return 3

    bars_5m = load_5m_bars(csv_path)
    if not bars_5m:
        print("No usable bars loaded")
        return 4

    as_of = getattr(bars_5m[-1], "ts_utc", None) or datetime.now(timezone.utc)

    print("=" * 70)
    print("REA - RegimeGate Proper Invocation")
    print("Bars supplied:", len(bars_5m))
    print("As-of UTC:", as_of)
    print("=" * 70)

    try:
        result = gate.evaluate(bars_5m=bars_5m, as_of_utc=as_of)
    except Exception as e:
        print("RegimeGate.evaluate FAILED:", repr(e))
        return 5

    print("\n[Raw Result]")
    print(result)

    allow = None
    reason = None

    if isinstance(result, bool):
        allow = result
    elif isinstance(result, dict):
        allow = bool(result.get("allow"))
        reason = result.get("reason") or result.get("block_reason")

    print("\n[Decision]")
    print("ALLOW:", allow)
    if reason:
        print("Reason:", reason)

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
