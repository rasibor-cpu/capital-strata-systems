"""Bridge MI-EXT events into existing GIE IntelligenceEvent without replacing GIE.

Authoritative integration boundary:
- MI-EXT owns catalogue, provenance, dedup, freshness, and advisory impact.
- GIE remains the existing global-intelligence event model/consumer.
- This bridge is an optional adapter only — not a second scheduler, store, or
  decision/execution engine.
- Fail-safe: if GIE models are unavailable, bridging returns None and never
  mutates execution state.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.intelligence.external_events.constants import UNAVAILABLE, UNKNOWN
from backend.intelligence.external_events.models import ExternalEvent

_GIE_IMPORT_ERROR: Exception | None = None
try:
    from backend.intelligence.global_intelligence.event_models import (
        EventCategory,
        EventSeverity,
        EventState,
        IntelligenceEvent,
    )
except Exception as exc:  # noqa: BLE001 — optional fail-safe
    EventCategory = None  # type: ignore[assignment]
    EventSeverity = None  # type: ignore[assignment]
    EventState = None  # type: ignore[assignment]
    IntelligenceEvent = None  # type: ignore[assignment]
    _GIE_IMPORT_ERROR = exc


_CATEGORY_MAP_NAMES = {
    "monetary_policy": "MONETARY_POLICY",
    "interest_rates": "MONETARY_POLICY",
    "inflation": "INFLATION",
    "employment": "EMPLOYMENT",
    "regulatory_action": "REGULATORY",
    "crypto_regulation": "REGULATORY",
    "issuer_earnings": "EARNINGS",
    "exchange_outage": "EXCHANGE",
    "market_disruption": "LIQUIDITY",
    "sanctions_geopolitics": "GEOPOLITICAL",
}


def gie_available() -> bool:
    return IntelligenceEvent is not None and _GIE_IMPORT_ERROR is None


def to_gie_event(event: ExternalEvent) -> Any | None:
    """Adapt one MI-EXT event into GIE IntelligenceEvent, or None if unavailable/unsafe."""
    if not gie_available():
        return None
    if event.execution_allowed or not event.advisory_only:
        return None

    published = event.published_at
    if published in {"", UNKNOWN, UNAVAILABLE}:
        # Do not invent timestamps — fail closed for bridge projection
        return None
    try:
        ts = datetime.fromisoformat(published.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
    except ValueError:
        return None

    confidence = 0.0 if event.confidence is None else float(event.confidence) * 100.0
    cat_name = _CATEGORY_MAP_NAMES.get(event.event_category, "UNKNOWN")
    category = getattr(EventCategory, cat_name, EventCategory.UNKNOWN)
    severity = EventSeverity.MODERATE
    if event.impact_magnitude == "high":
        severity = EventSeverity.HIGH
    if event.event_category in {"exchange_outage", "market_disruption"}:
        severity = EventSeverity.SEVERE
    return IntelligenceEvent(
        event_id=event.event_id,
        timestamp=ts,
        title=event.title,
        category=category,
        severity=severity,
        confidence=confidence,
        source=event.source_name,
        affected_assets=list(event.affected_instruments),
        description=event.normalized_summary,
        event_state=EventState.NEW,
    )
