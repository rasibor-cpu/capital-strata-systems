from __future__ import annotations

from typing import Iterable

from .event_models import EventCategory, EventSeverity, IntelligenceEvent, RegimeState


def determine_regime(active_events: Iterable[IntelligenceEvent]) -> RegimeState:
    events = [event for event in active_events if event.active]
    if not events:
        return RegimeState.NORMAL

    highest_severity = max(events, key=lambda item: item.severity.value)
    has_severe_risk = any(
        event.severity in (EventSeverity.SEVERE, EventSeverity.CRITICAL)
        for event in events
    )
    has_liquidity_or_exchange = any(
        event.category in (EventCategory.LIQUIDITY, EventCategory.EXCHANGE)
        and event.severity in (EventSeverity.SEVERE, EventSeverity.CRITICAL)
        for event in events
    )
    has_high_confidence_earnings = any(
        event.category == EventCategory.EARNINGS and event.confidence >= 70.0 and event.severity in (EventSeverity.LOW, EventSeverity.MODERATE, EventSeverity.HIGH)
        for event in events
    )
    has_critical_confidence = any(
        event.severity == EventSeverity.CRITICAL and event.confidence >= 75.0
        for event in events
    )
    has_defensive_confidence = any(
        event.severity == EventSeverity.HIGH and event.confidence >= 60.0
        for event in events
    )

    if has_liquidity_or_exchange:
        return RegimeState.LIQUIDITY_CRISIS

    if has_critical_confidence or (has_severe_risk and any(event.confidence >= 70.0 for event in events)):
        return RegimeState.PANIC

    if has_high_confidence_earnings and not has_severe_risk:
        return RegimeState.OPPORTUNITY_EXPANSION

    if has_defensive_confidence:
        return RegimeState.DEFENSIVE

    if all(event.severity in (EventSeverity.LOW, EventSeverity.MODERATE) for event in events):
        return RegimeState.CAUTION

    if highest_severity == EventSeverity.HIGH:
        return RegimeState.DEFENSIVE

    return RegimeState.CAUTION