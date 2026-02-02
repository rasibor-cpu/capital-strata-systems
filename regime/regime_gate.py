"""
REA Capital — RegimeGate Intel Overlay
Phase 6.4 (SAFE WRAPPER)

Goal:
- Accept existing regime decision (ALLOW/BLOCK) from the base regime gate
- Apply a deterministic "intel pressure overlay" using RegimeSignal objects
- Produce a final decision + rationale
- NO execution, NO trading

This wrapper is intentionally non-invasive:
- You keep regime/regime_gate.py unchanged
- This module sits in front of it

Later, once validated, we can merge into the main gate as a full replacement.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from engine.regime_signal import RegimeSignal


# -----------------------------
# Decision model (generic)
# -----------------------------

@dataclass(frozen=True)
class GateDecision:
    ts_utc: str
    base_decision: str          # e.g. "ALLOW" / "BLOCK"
    final_decision: str         # e.g. "ALLOW" / "BLOCK" / "TIGHTEN"
    pressure: float             # 0..1 combined intel pressure
    confidence: float           # 0..1 combined intel confidence
    reason: str
    meta: Dict[str, Any]


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp01(x: float) -> float:
    try:
        x = float(x)
    except Exception:
        return 0.0
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return round(x, 3)


# -----------------------------
# Intel aggregation policy
# -----------------------------
"""
Policy (deterministic):
- Each RegimeSignal contributes: weight * pressure
- We combine pressures as weighted average
- We combine confidence as weighted average
- We then apply thresholds:

Default thresholds:
- If base is BLOCK -> final stays BLOCK
- If combined_pressure >= 0.85 and confidence >= 0.70 -> final BLOCK (risk spike)
- If combined_pressure >= 0.65 and confidence >= 0.60 -> final TIGHTEN (risk caution)
- Else -> final stays base

"TIGHTEN" means downstream modules reduce risk (size, leverage, frequency, etc.)
without blocking completely.
"""

DEFAULT_WEIGHTS = {
    "macro": 0.55,
    "news": 0.45,
    # Future-proof:
    "volatility": 0.60,
    "liquidity": 0.60,
    "policy": 0.55,
}

THRESH_BLOCK = 0.85
THRESH_TIGHTEN = 0.65


def aggregate_intel(signals: List[RegimeSignal]) -> (float, float, Dict[str, Any]):
    if not signals:
        return 0.0, 0.0, {"count": 0, "by_source": {}}

    total_w = 0.0
    sum_p = 0.0
    sum_c = 0.0

    by_source: Dict[str, int] = {}

    for s in signals:
        # signal_class is "macro" / "news" in our router
        w = DEFAULT_WEIGHTS.get(s.signal_class, 0.40)
        p = _clamp01(s.pressure)
        c = _clamp01(s.confidence)

        total_w += w
        sum_p += w * p
        sum_c += w * c

        by_source[s.source] = by_source.get(s.source, 0) + 1

    if total_w <= 0:
        return 0.0, 0.0, {"count": len(signals), "by_source": by_source}

    pressure = _clamp01(sum_p / total_w)
    confidence = _clamp01(sum_c / total_w)

    meta = {
        "count": len(signals),
        "by_source": by_source,
        "weights": DEFAULT_WEIGHTS,
        "thresholds": {"block": THRESH_BLOCK, "tighten": THRESH_TIGHTEN},
    }
    return pressure, confidence, meta


def apply_overlay(
    *,
    base_decision: str,
    signals: List[RegimeSignal],
) -> GateDecision:
    base = (base_decision or "").upper().strip()
    if base not in {"ALLOW", "BLOCK"}:
        base = "ALLOW"  # fail-safe default (caller should be explicit)

    # base BLOCK always wins
    if base == "BLOCK":
        return GateDecision(
            ts_utc=_now_utc(),
            base_decision=base,
            final_decision="BLOCK",
            pressure=0.0,
            confidence=0.0,
            reason="Base regime gate blocked; overlay not applied",
            meta={"overlay_applied": False},
        )

    pressure, confidence, meta = aggregate_intel(signals)

    # Decide overlay action
    if pressure >= THRESH_BLOCK and confidence >= 0.70:
        final = "BLOCK"
        reason = "Intel overlay: high risk pressure"
    elif pressure >= THRESH_TIGHTEN and confidence >= 0.60:
        final = "TIGHTEN"
        reason = "Intel overlay: elevated risk pressure"
    else:
        final = base
        reason = "Intel overlay: no change"

    return GateDecision(
        ts_utc=_now_utc(),
        base_decision=base,
        final_decision=final,
        pressure=pressure,
        confidence=confidence,
        reason=reason,
        meta={**meta, "overlay_applied": True},
    )


# -----------------------------
# Self-test
# -----------------------------

if __name__ == "__main__":
    # Example: macro tightening + news risk_off
    s1 = RegimeSignal.now(
        source="fred",
        signal_class="macro",
        regime_dimension="risk",
        pressure=0.72,
        confidence=0.95,
        direction="tightening",
        raw_ref="demo-fred",
        meta={"series_id": "DGS10"},
    )
    s2 = RegimeSignal.now(
        source="gdelt",
        signal_class="news",
        regime_dimension="risk",
        pressure=0.85,
        confidence=0.80,
        direction="risk_off",
        raw_ref="demo-gdelt",
        meta={"tone": -3.5},
    )

    d = apply_overlay(base_decision="ALLOW", signals=[s1, s2])
    print("REGIME_INTEL_OVERLAY_OK")
    print(asdict(d))
