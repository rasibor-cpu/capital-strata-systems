"""
run_prompts_regime_aware.py — REA Capital (PROMPT-ONLY)
No edits to engine_loop.py.

Flow:
- Load 1m CSV
- Aggregate to 5m bars
- Call RegimeGate.evaluate(bars_5m, as_of_utc) correctly
- If ALLOW: compute VWAP and call build_vwap_prompt_default_eps
- Print prompts + write audit events

Inputs expected:
- sample_spy_1m_long.csv (preferred)
- Produces prompts to console (and audit logs)
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional
from collections import deque


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
class Bar1m:
    ts_utc: Any
    c: float
    v: float = 1.0


@dataclass
class Bar5m:
    ts_utc: Any
    c: float
    v: float = 1.0


def floor_to_5m(dt: datetime) -> datetime:
    minute = (dt.minute // 5) * 5
    return dt.replace(minute=minute, second=0, microsecond=0)


def load_1m(csv_path: str) -> List[Bar1m]:
    bars: List[Bar1m] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            ts_s = row.get("ts_utc") or row.get("timestamp")
            close_s = row.get("c") or row.get("close")
            vol_s = row.get("v") or row.get("volume")
            if not ts_s or not close_s:
                continue
            ts = parse_ts(ts_s) or ts_s
            c = float(close_s)
            v = float(vol_s) if vol_s else 1.0
            bars.append(Bar1m(ts_utc=ts, c=c, v=v))
    return bars


def agg_5m(bars_1m: List[Bar1m]) -> List[Bar5m]:
    buckets: Dict[str, Dict[str, Any]] = {}
    for b in bars_1m:
        if not isinstance(b.ts_utc, datetime):
            continue
        kdt = floor_to_5m(b.ts_utc)
        key = kdt.isoformat()

        if key not in buckets:
            buckets[key] = {"ts_utc": kdt, "last_ts": b.ts_utc, "c": b.c, "v": b.v}
        else:
            if b.ts_utc >= buckets[key]["last_ts"]:
                buckets[key]["last_ts"] = b.ts_utc
                buckets[key]["c"] = b.c
            buckets[key]["v"] += b.v

    out = [Bar5m(ts_utc=v["ts_utc"], c=float(v["c"]), v=float(v["v"])) for k, v in sorted(buckets.items())]
    return out


def compute_vwap(window: Deque[Bar1m]) -> Optional[float]:
    pv = 0.0
    vol = 0.0
    for b in window:
        pv += float(b.c) * float(b.v)
        vol += float(b.v)
    return (pv / vol) if vol > 0 else None


def main() -> int:
    # audit (optional)
    audit = None
    try:
        from engine.security.access_audit_log import AccessAuditLogger  # type: ignore
        audit = AccessAuditLogger()
        audit.write("session_start", {"runner": "run_prompts_regime_aware"})
    except Exception:
        audit = None

    # imports
    try:
        from regime.gate import RegimeGate  # type: ignore
    except Exception as e:
        print("FAILED to import RegimeGate:", repr(e))
        return 2

    try:
        from signals.vwap_mean_reversion import build_vwap_prompt_default_eps  # type: ignore
    except Exception as e:
        print("FAILED to import VWAP prompt builder:", repr(e))
        return 3

    csv_path = "sample_spy_1m_long.csv" if os.path.exists("sample_spy_1m_long.csv") else "sample_spy_1m.csv"
    if not os.path.exists(csv_path):
        print("Missing 1m CSV input.")
        return 4

    bars_1m = load_1m(csv_path)
    if len(bars_1m) < 10:
        print("Not enough 1m bars.")
        return 5

    # build 5m history and evaluate regime
    bars_5m = agg_5m(bars_1m)
    as_of = None
    for b in reversed(bars_5m):
        if isinstance(b.ts_utc, datetime):
            as_of = b.ts_utc
            break
    as_of = as_of or datetime.now(timezone.utc)

    gate = RegimeGate()
    try:
        r = gate.evaluate(bars_5m=bars_5m, as_of_utc=as_of)
    except Exception as e:
        print("RegimeGate.evaluate FAILED:", repr(e))
        if audit:
            audit.write("blocked_regime", {"error": repr(e)})
        return 6

    # infer allow
    allow = None
    reasons = None
    if hasattr(r, "decision"):
        allow = str(getattr(r, "decision")).upper().endswith("ALLOW")
    if hasattr(r, "reasons"):
        reasons = getattr(r, "reasons")
    if isinstance(r, dict) and "allow" in r:
        allow = bool(r.get("allow"))
        reasons = r.get("reasons") or r.get("reason")

    print("=" * 70)
    print("Regime decision:", r)
    print("ALLOW:", allow)
    print("Reasons:", reasons)
    print("=" * 70)

    if audit:
        audit.write("regime_eval", {"allow": allow, "reasons": str(reasons)})

    if not allow:
        print("Regime blocked — no prompts.")
        if audit:
            audit.write("session_end", {"prompts_generated": 0})
        return 0

    # prompt generation (prompt-only)
    window = deque(maxlen=5)
    prompts = 0
    eps_pct = 0.0001

    for b in bars_1m:
        window.append(b)
        if len(window) < 5:
            continue

        vwap = compute_vwap(window)
        if vwap is None:
            continue

        prompt = build_vwap_prompt_default_eps(
            price=float(b.c),
            vwap=float(vwap),
            pct=float(eps_pct),
            extra={"as_of_utc": str(b.ts_utc), "window": 5, "source_csv": csv_path},
        )

        if isinstance(prompt, dict):
            prompts += 1
            print(prompt)
            if audit:
                audit.write("prompt_generated", {"count": prompts})

    print(f"\nDone. Prompts generated: {prompts}")
    if audit:
        audit.write("session_end", {"prompts_generated": prompts})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())