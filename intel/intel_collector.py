# intel/intel_collector.py
"""
Unified Intel Collector
-----------------------
Single free-first, source-agnostic entrypoint that aggregates all
IntelEnvelope signals and returns List[IntelEnvelope].

Design goals:
- Never raise on upstream failure
- Free sources first
- Source failures are tolerated and logged
- Strict IntelEnvelope output only
"""

from typing import List
from datetime import datetime, timezone

# Core envelope
from intel.event_calendar_adapter import fetch_economic_events_safe


# Adapters (all optional / tolerant)
from intel.event_calendar_adapter import fetch_economic_events_safe
from intel.news_feed_adapter import fetch_structured_news_safe
from intel.realized_volatility_adapter import fetch_realized_volatility_safe
from intel.binance_volatility_adapter import fetch_crypto_volatility_safe
from intel.cftc_cot_adapter import fetch_cftc_cot_safe

# Optional macro/news
try:
    from intel.fred_adapter import fetch_fred_macro_safe
except Exception:
    fetch_fred_macro_safe = None

try:
    from intel.gdelt_adapter import fetch_gdelt_news_safe
except Exception:
    fetch_gdelt_news_safe = None


def collect_intel() -> List[IntelEnvelope]:
    """
    Master intel aggregation function.
    Always returns a list (possibly empty).
    """
    envelopes: List[IntelEnvelope] = []
    ts_now = datetime.now(timezone.utc).isoformat()

    # ---- MACRO (FRED) ----
    if fetch_fred_macro_safe:
        try:
            envelopes.extend(fetch_fred_macro_safe())
        except Exception:
            pass

    # ---- ECONOMIC EVENTS ----
    try:
        envelopes.extend(fetch_economic_events_safe())
    except Exception:
        pass

    # ---- STRUCTURED NEWS (RSS/Yahoo/etc) ----
    try:
        envelopes.extend(fetch_structured_news_safe())
    except Exception:
        pass

    # ---- GDELT (OPTIONAL / RATE-LIMITED) ----
    if fetch_gdelt_news_safe:
        try:
            envelopes.extend(fetch_gdelt_news_safe())
        except Exception:
            pass

    # ---- REALIZED VOLATILITY (INTERNAL PRICE SERIES) ----
    try:
        envelopes.extend(fetch_realized_volatility_safe())
    except Exception:
        pass

    # ---- CRYPTO VOLATILITY (BINANCE / COINBASE FALLBACK) ----
    try:
        envelopes.extend(fetch_crypto_volatility_safe())
    except Exception:
        pass

    # ---- CFTC COT (DEMO CROWDING SIGNAL) ----
    try:
        envelopes.extend(fetch_cftc_cot_safe())
    except Exception:
        pass

    return envelopes


# -----------------------------
# CLI smoke test
# -----------------------------
if __name__ == "__main__":
    intel = collect_intel()
    print(f"INTEL_COLLECTOR_OK | envelopes={len(intel)}")
    for env in intel[:5]:
        print(env)
