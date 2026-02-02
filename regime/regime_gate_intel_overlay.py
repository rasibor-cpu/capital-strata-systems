"""
Regime Gate Intel Overlay (SAFE, RATE-LIMIT HARDENED)
----------------------------------------------------
- Converts intel sources into IntelEnvelope
- Routes IntelEnvelope -> RegimeSignal
- Aggregates pressure and returns ALLOW/TIGHTEN/BLOCK

Resilience:
- News fetch failures (e.g., GDELT 429) MUST NOT crash the engine.
- If news unavailable, proceed with macro-only intel.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import List, Dict, Any

from engine.intel_router import route_intel_envelope
from engine.regime_signal import RegimeSignal

from intel.fred_to_envelope import fred_record_to_envelope

# GDELT is optional at runtime (may rate-limit)
try:
    from intel.gdelt_adapter import fetch_gdelt_headlines
    from intel.gdelt_to_envelope import gdelt_headline_to_envelope
    GDELT_AVAILABLE = True
except Exception:
    GDELT_AVAILABLE = False


def _utc_now() -> str:
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


def apply_intel_overlay(base: Dict[str, Any], intel_envelopes: List[Any]) -> Dict[str, Any]:
    base_pressure = _clamp01(base.get("pressure", 0.0))
    base_conf = _clamp01(base.get("confidence", 0.0))
    base_decision = (base.get("decision") or "ALLOW").upper()

    if base_decision == "BLOCK":
        return {
            "ts_utc": _utc_now(),
            "base_decision": "BLOCK",
            "final_decision": "BLOCK",
            "base_pressure": base_pressure,
            "overlay_pressure": base_pressure,
            "confidence": base_conf,
            "signals_used": 0,
            "reason": "Base regime decision BLOCK; overlay not applied",
        }

    signals: List[RegimeSignal] = [route_intel_envelope(env) for env in intel_envelopes]

    overlay_pressure = base_pressure
    overlay_conf = base_conf

    for s in signals:
        overlay_pressure = max(overlay_pressure, _clamp01(s.pressure))
        overlay_conf = max(overlay_conf, _clamp01(s.confidence))

    if overlay_pressure >= 0.85 and overlay_conf >= 0.70:
        final = "BLOCK"
        reason = "Intel overlay: high risk pressure"
    elif overlay_pressure >= 0.70 and overlay_conf >= 0.60:
        final = "TIGHTEN"
        reason = "Intel overlay: elevated risk pressure"
    else:
        final = "ALLOW"
        reason = "Intel overlay: no change"

    return {
        "ts_utc": _utc_now(),
        "base_decision": base_decision,
        "final_decision": final,
        "base_pressure": base_pressure,
        "overlay_pressure": overlay_pressure,
        "confidence": overlay_conf,
        "signals_used": len(signals),
        "signals": [s.to_dict() for s in signals],
        "reason": reason,
    }


def _safe_fetch_news_envelopes() -> (List[Any], str):
    """
    Fetch GDELT news and convert to IntelEnvelope.
    Must never raise.
    Returns: (news_envs, status_msg)
    """
    if not GDELT_AVAILABLE:
        return [], "gdelt_unavailable"

    try:
        headlines = fetch_gdelt_headlines(
            query="(fed OR rates OR inflation) AND (market OR stocks OR bonds)",
            minutes=360,
            max_items=3,
        )
        envs = [gdelt_headline_to_envelope(asdict(h)) for h in headlines]
        return envs, f"gdelt_ok:{len(envs)}"
    except Exception as e:
        # Includes 429 rate limit, network errors, JSON issues
        return [], f"gdelt_fail:{type(e).__name__}"


# -----------------------------
# Self-test harness
# -----------------------------
if __name__ == "__main__":
    print("REGIME_INTEL_OVERLAY_OK")

    base = {"decision": "ALLOW", "pressure": 0.62, "confidence": 0.80}

    fred_sample = {
        "series_id": "DGS10",
        "value": 5.28,
        "observation_date": "2026-01-01",
        "frequency": "daily",
        "source_quality": "official",
    }
    fred_env = fred_record_to_envelope(fred_sample)

    news_envs, news_status = _safe_fetch_news_envelopes()

    envelopes = [fred_env] + news_envs

    result = apply_intel_overlay(base, envelopes)
    result["news_status"] = news_status
    print(result)
