"""
test_vwap_live_dryrun.py | REA Capital
Purpose:
- Live-data (CSV) dry-run: RegimeGate + VWAP signal generation
- LOG-ONLY (no execution, no orders)
- Confirms end-to-end: load bars -> regime allow -> signal(s)
"""

from __future__ import annotations

import csv
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

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


def load_5m_bars_for_vwap(csv_path: str) -> List[Dict[str, Any]]:
    """
    Load 5m bars into VWAP-signal dict schema:
      ts, h, l, c, v
    Accepts common CSV headers:
      ts_utc/timestamp, high/low/close, h/l/c, volume/v
    """
    bars: List[Dict[str, Any]] = []
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

            bars.append({"ts": ts, "h": h, "l": l, "c": c, "v": v})
    return bars


def main() -> int:
    csv_path = "sample_spy_5m.csv"
    if not os.path.exists(csv_path):
        print("Missing sample_spy_5m.csv")
        print("Put a 5-minute CSV in project root named sample_spy_5m.csv and rerun.")
        return 2

    bars = load_5m_bars_for_vwap(csv_path)
    if len(bars) < 20:
        print("Not enough usable bars loaded:", len(bars))
        print("Need at least 20 for lookback.")
        return 3

    as_of = bars[-1]["ts"]

    print("=" * 70)
    print("REA – Live Dry Run (CSV) — RegimeGate + VWAP (LOG ONLY)")
    print("Bars loaded:", len(bars))
    print("As-of UTC:", as_of)
    print("=" * 70)

    # 1) Regime gate check (uses bars_5m; it may accept dicts or objects depending on implementation)
    gate = RegimeGate()
    try:
        rg = gate.evaluate(bars_5m=bars, as_of_utc=as_of)  # type: ignore
    except Exception as e:
        print("RegimeGate.evaluate FAILED:", repr(e))
        print("Note: your RegimeGate may require attribute-style bars; if so we will adapt safely next step.")
        return 4

    print("\n[RegimeGate Raw]")
    print(rg)

    # Interpret decision
    allow = None
    if isinstance(rg, bool):
        allow = rg
    elif isinstance(rg, dict):
        allow = bool(rg.get("allow"))
    elif hasattr(rg, "decision"):
        d = str(getattr(rg, "decision", "")).upper()
        allow = ("ALLOW" in d) and ("BLOCK" not in d)

    print("\n[RegimeGate Decision]")
    print("ALLOW:", allow)

    # 2) VWAP signals (log only)
    print("\n[VWAP Signals]")
    signals = generate_vwap_mean_reversion_signals(
        bars_5m=bars,
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
