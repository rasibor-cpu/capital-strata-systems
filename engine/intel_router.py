"""
Intel Router
------------
Routes all IntelEnvelope inputs into RegimeSignal objects.

Supports:
- Macro (FRED)
- News (GDELT / structured feeds)
- Volatility (realized, broker-agnostic)
- Future sources: Reuters, Bloomberg (via envelope only)

RULE:
- Router ONLY accepts IntelEnvelope
- Router ALWAYS emits RegimeSignal
"""

from datetime import datetime, timezone
from typing import Optional

from engine.regime_signal import RegimeSignal
from intel.intel_envelope import IntelEnvelope

# Existing adapters
from intel.fred_to_envelope import fred_record_to_envelope
from intel.gdelt_adapter import fetch_gdelt_headlines

# NEW: Realized volatility
from intel.realized_volatility_adapter import compute_vol_signal


def route_intel_envelope(env: IntelEnvelope) -> RegimeSignal:
    """
    Core routing function.
    Converts IntelEnvelope -> RegimeSignal.
    """

    if not isinstance(env, IntelEnvelope):
        raise TypeError("route_intel_envelope expects IntelEnvelope")

    # -------------------------------
    # MACRO (FRED)
    # -------------------------------
    if env.signal_class == "macro":
        return RegimeSignal(
            ts_utc=env.ts_utc,
            source=env.provider,
            signal_class="macro",
            regime_dimension="risk",
            pressure=env.severity,
            confidence=env.confidence,
            direction="tightening" if env.severity >= 0.6 else "loosening",
            raw_ref=env.intel_id,
            meta={"signal_class": env.signal_class, "raw": env.raw_payload},
        )

    # -------------------------------
    # NEWS (GDELT / STRUCTURED)
    # -------------------------------
    if env.signal_class == "news":
        tone = env.raw_payload.get("tone", 0.0)

        return RegimeSignal(
            ts_utc=env.ts_utc,
            source=env.provider,
            signal_class="news",
            regime_dimension="risk",
            pressure=min(abs(tone) / 5.0, 1.0),
            confidence=env.confidence,
            direction="risk-off" if tone < -1.5 else "neutral",
            raw_ref=env.intel_id,
            meta={"tone": tone, "raw": env.raw_payload},
        )

    # -------------------------------
    # VOLATILITY (REALIZED)
    # -------------------------------
    if env.signal_class == "volatility":
        # Already normalized by adapter
        return RegimeSignal(
            ts_utc=env.ts_utc,
            source=env.provider,
            signal_class="volatility",
            regime_dimension="risk",
            pressure=env.severity,
            confidence=env.confidence,
            direction="risk-off" if env.severity >= 0.6 else "neutral",
            raw_ref=env.intel_id,
            meta={"volatility": env.raw_payload},
        )

    # -------------------------------
    # FALLBACK
    # -------------------------------
    return RegimeSignal(
        ts_utc=datetime.now(timezone.utc).isoformat(),
        source=env.provider,
        signal_class="unknown",
        regime_dimension="risk",
        pressure=0.0,
        confidence=0.0,
        direction="neutral",
        raw_ref=env.intel_id,
        meta={"note": "Unhandled signal_class"},
    )


# ---------------------------------------------------
# CLI sanity test
# ---------------------------------------------------
if __name__ == "__main__":
    print("INTEL_ROUTER_READY")
