# intel/gdelt_to_envelope.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Any

from intel.intel_envelope import IntelEnvelope


def gdelt_headline_to_envelope(headline: Dict[str, Any]) -> IntelEnvelope:
    """
    Convert a single GDELT headline record into a normalized IntelEnvelope.

    This enforces the invariant:
        ALL intel routed into the engine MUST be IntelEnvelope.
    """

    # --- Extract tone / sentiment ---
    tone = headline.get("tone")
    try:
        tone = float(tone)
    except (TypeError, ValueError):
        tone = 0.0

    # --- Map tone → pressure (absolute intensity) ---
    pressure = min(abs(tone) / 10.0, 1.0)

    # --- Direction mapping ---
    if tone < -0.5:
        direction = "risk-off"
    elif tone > 0.5:
        direction = "risk-on"
    else:
        direction = "neutral"

    # --- Confidence heuristic ---
    confidence = 0.80 if abs(tone) >= 1.0 else 0.65

    return IntelEnvelope(
        ts_utc=datetime.now(timezone.utc).isoformat(),
        provider="gdelt",
        intel_type="news",
        signal_class="news",
        instrument_scope="GLOBAL",
        pressure=round(pressure, 3),
        direction=direction,
        confidence=confidence,
        severity=round(pressure * confidence, 3),
        meta={
            "tone": tone,
            "title": headline.get("title"),
            "domain": headline.get("domain"),
            "url": headline.get("url"),
            "language": headline.get("language"),
            "raw": headline,
        },
    )
