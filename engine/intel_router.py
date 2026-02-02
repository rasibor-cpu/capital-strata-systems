"""
REA Capital — Intel Router
Phase 6.3

Routes IntelEnvelope objects into RegimeSignal outputs.
This is the ONLY intelligence bridge into RegimeGate.

Design principles:
- Provider-agnostic (FRED, GDELT, Reuters, Bloomberg, etc.)
- Deterministic
- Fail-closed
- No execution logic
"""

from intel.intel_envelope import IntelEnvelope
from engine.regime_signal import RegimeSignal


def _route_macro(env: IntelEnvelope) -> RegimeSignal:
    signal_class = env.signal_class

    if signal_class in {"rates", "policy"}:
        dimension = "risk"
        direction = "tightening" if env.severity >= 0.6 else "easing"
    elif signal_class == "inflation":
        dimension = "inflation"
        direction = "rising" if env.severity >= 0.6 else "stable"
    else:
        raise ValueError(f"Unsupported macro signal_class '{signal_class}'")

    return RegimeSignal.now(
        source=env.provider,
        signal_class="macro",
        regime_dimension=dimension,
        pressure=env.severity,
        confidence=env.confidence,
        direction=direction,
        raw_ref=env.intel_id,
        meta={"signal_class": env.signal_class, "raw": env.raw},
    )


def _route_news(env: IntelEnvelope) -> RegimeSignal:
    tone = (env.raw or {}).get("tone")
    shock = env.severity

    if shock >= 0.7:
        direction = "risk_off"
    elif shock <= 0.3:
        direction = "risk_on"
    else:
        direction = "neutral"

    return RegimeSignal.now(
        source=env.provider,
        signal_class="news",
        regime_dimension="risk",
        pressure=shock,
        confidence=env.confidence,
        direction=direction,
        raw_ref=env.intel_id,
        meta={"tone": tone, "raw": env.raw},
    )


def route_intel(env: IntelEnvelope) -> RegimeSignal:
    """
    Primary public router entrypoint.
    """
    if not isinstance(env, IntelEnvelope):
        raise TypeError("route_intel expects IntelEnvelope")

    if env.intel_type == "macro":
        return _route_macro(env)

    if env.intel_type == "news":
        return _route_news(env)

    raise ValueError(f"Unsupported intel_type '{env.intel_type}'")


# Stable alias (future-proof for other modules / providers)
def route_intel_envelope(env: IntelEnvelope) -> RegimeSignal:
    """
    Stable alias for route_intel (do not remove).
    """
    return route_intel(env)


# Self-test
if __name__ == "__main__":
    macro_env = IntelEnvelope.create(
        provider="fred",
        intel_type="macro",
        signal_class="rates",
        instrument_scope="GLOBAL",
        confidence=0.95,
        severity=0.72,
        raw={"series_id": "DGS10"},
    )

    news_env = IntelEnvelope.create(
        provider="gdelt",
        intel_type="news",
        signal_class="geopolitical",
        instrument_scope="GLOBAL",
        confidence=0.80,
        severity=0.85,
        raw={"tone": -3.5},
    )

    print("INTEL_ROUTER_MACRO_OK")
    print(route_intel(macro_env).to_dict())

    print("INTEL_ROUTER_NEWS_OK")
    print(route_intel(news_env).to_dict())
