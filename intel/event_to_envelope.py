"""
Event → IntelEnvelope transformer
---------------------------------
Normalizes economic calendar events into IntelEnvelope objects
so they can flow through IntelRouter and Regime overlays.

PHASE 7.6 — Event intelligence normalization
"""

from datetime import datetime, timezone
from typing import Dict, Optional

# ✅ Correct location in this repo:
from intel.intel_envelope import IntelEnvelope


def event_to_envelope(event: Dict) -> Optional[IntelEnvelope]:
    """
    Convert a raw economic calendar event dict into IntelEnvelope.
    Fail-closed: returns None if unusable.
    """
    try:
        ts_raw = event.get("ts_utc") or event.get("timestamp")

        if isinstance(ts_raw, (int, float)):
            ts_utc = datetime.fromtimestamp(ts_raw, tz=timezone.utc)
        elif isinstance(ts_raw, str):
            ts_utc = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
        else:
            ts_utc = datetime.now(tz=timezone.utc)

        impact = (event.get("impact") or "").lower().strip()

        # Impact → severity mapping (deterministic)
        severity_map = {"low": 0.15, "medium": 0.40, "high": 0.75}
        severity = severity_map.get(impact, 0.30)

        # Confidence heuristic
        confidence = 0.60
        if impact == "high":
            confidence = 0.80
        elif impact == "medium":
            confidence = 0.65

        raw = {
            "event": event.get("event") or event.get("title"),
            "country": event.get("country"),
            "currency": event.get("currency"),
            "impact": impact,
            "actual": event.get("actual"),
            "forecast": event.get("forecast"),
            "previous": event.get("previous"),
            "source": event.get("source", "economic_calendar"),
        }

        # Use canonical factory (consistent with FRED/GDELT/COT)
        return IntelEnvelope.create(
            provider=raw["source"],
            intel_type="event",
            signal_class="scheduled_risk",
            instrument_scope=(raw.get("currency") or "GLOBAL"),
            raw=raw,
            confidence=confidence,
            severity=severity,
            rea_instrument=None,
        )
    except Exception:
        return None


def _self_test():
    sample = {
        "ts_utc": "2026-02-03T00:00:00Z",
        "country": "US",
        "currency": "USD",
        "event": "Non-Farm Payrolls",
        "impact": "high",
        "forecast": "185K",
        "previous": "216K",
        "source": "economic_calendar",
    }

    env = event_to_envelope(sample)
    print("EVENT_ENVELOPE_OK" if env else "EVENT_ENVELOPE_FAILED")
    print(env)


if __name__ == "__main__":
    _self_test()
