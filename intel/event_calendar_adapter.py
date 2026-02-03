# intel/event_calendar_adapter.py
"""
Economic Event Calendar Adapter (FREE)
Contract:
- Exports fetch_economic_events_safe()
- Never raises
- Returns List[IntelEnvelope]
"""

from datetime import datetime, timezone
from typing import List

from intel.intel_envelope import IntelEnvelope


def fetch_economic_events_safe() -> List[IntelEnvelope]:
    """
    Safe economic events fetcher (placeholder mode).
    Always returns a list (possibly empty).
    """
    out: List[IntelEnvelope] = []

    try:
        out.append(
            IntelEnvelope.create(
                provider="economic_calendar",
                intel_type="event",
                signal_class="scheduled_risk",
                instrument_scope="GLOBAL",
                raw={
                    "event_type": "macro_calendar",
                    "impact": "scheduled",
                    "note": "Free economic calendar placeholder",
                },
                confidence=0.60,
                severity=0.25,
                rea_instrument=None,
            )
        )
    except Exception:
        return []

    return out


if __name__ == "__main__":
    events = fetch_economic_events_safe()
    print(f"ECON_EVENTS_OK: {len(events)}")
    for e in events:
        print(e)
