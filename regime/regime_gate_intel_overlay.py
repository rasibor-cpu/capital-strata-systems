
"""
Intel → Regime Gate Overlay
---------------------------
Source-agnostic intelligence overlay that adjusts regime pressure
based on routed IntelSignals (macro, news, etc).

This file is intentionally separate from regime_gate.py
to allow future providers (Reuters, Bloomberg, ICE, etc)
to plug in without modifying the core gate.
"""

from datetime import datetime, timezone
from engine.regime_signal import RegimeSignal
from engine.intel_router import route_intel_envelope


def apply_intel_overlay(base_decision: dict, intel_envelopes: list) -> dict:
    """
    Adjust base regime decision using routed intel signals.
    """
    pressure = base_decision.get("pressure", 0.0)
    confidence = base_decision.get("confidence", 0.0)

    signals = []

    for env in intel_envelopes:
        sig = route_intel_envelope(env)
        if sig:
            signals.append(sig)
            pressure = max(pressure, sig.pressure)
            confidence = max(confidence, sig.confidence)

    overlay = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "base_pressure": base_decision.get("pressure"),
        "overlay_pressure": pressure,
        "confidence": confidence,
        "signals_used": len(signals),
        "final_decision": "BLOCK" if pressure >= 0.85 else "TIGHTEN" if pressure >= 0.70 else "ALLOW"
    }

    return overlay


# ---- standalone test harness ----
if __name__ == "__main__":
    print("REGIME_INTEL_OVERLAY_OK")

    base = {
        "pressure": 0.62,
        "confidence": 0.8,
        "decision": "ALLOW"
    }

    from intel.fred_to_envelope import fred_record_to_envelope
    from intel.gdelt_adapter import fetch_gdelt_headlines

    # sample intel
    fred_sample = {
        "series_id": "DGS10",
        "value": 5.28,
        "observation_date": "2026-01-01",
        "frequency": "daily",
        "source_quality": "official"
    }

    gdelt_news = fetch_gdelt_headlines(
        query="(fed OR rates OR inflation)",
        minutes=180,
        max_items=3
    )

    envelopes = [fred_record_to_envelope(fred_sample)] + gdelt_news

    result = apply_intel_overlay(base, envelopes)
    print(result)
