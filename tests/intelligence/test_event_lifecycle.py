from datetime import datetime, timedelta

from backend.intelligence.global_intelligence.event_lifecycle_manager import EventLifecycleManager
from backend.intelligence.global_intelligence.event_models import (
    EventCategory,
    EventSeverity,
    EventState,
    IntelligenceEvent,
)


def test_event_lifecycle_transitions():
    manager = EventLifecycleManager()
    now = datetime.utcnow()
    event = IntelligenceEvent(
        event_id="event-lifecycle-1",
        timestamp=now - timedelta(days=2),
        title="Lifecycle test event",
        category=EventCategory.GEOPOLITICAL,
        severity=EventSeverity.HIGH,
        confidence=80.0,
        source="unit-test",
        affected_assets=["FX"],
        description="Testing lifecycle transitions.",
        expiration_time=now + timedelta(hours=1),
    )

    manager.transition_event(event, now=now)
    assert event.event_state in {EventState.MONITORING, EventState.STABILIZING}


def test_event_severity_downgrade_on_age():
    manager = EventLifecycleManager()
    now = datetime.utcnow()
    event = IntelligenceEvent(
        event_id="event-lifecycle-2",
        timestamp=now - timedelta(days=4),
        title="Severity downgrade test",
        category=EventCategory.REGULATORY,
        severity=EventSeverity.CRITICAL,
        confidence=90.0,
        source="unit-test",
        affected_assets=["BONDS"],
        description="Aged critical event.",
        expiration_time=now + timedelta(days=1),
    )

    manager.transition_event(event, now=now)
    assert event.severity == EventSeverity.SEVERE


def test_expired_event_moves_to_expired_state():
    manager = EventLifecycleManager()
    now = datetime.utcnow()
    event = IntelligenceEvent(
        event_id="event-lifecycle-3",
        timestamp=now - timedelta(days=1),
        title="Expired event",
        category=EventCategory.MONETARY_POLICY,
        severity=EventSeverity.MODERATE,
        confidence=60.0,
        source="unit-test",
        affected_assets=["FX"],
        description="Already expired.",
        expiration_time=now - timedelta(minutes=1),
    )

    manager.transition_event(event, now=now)
    assert event.active is False
    assert event.event_state == EventState.EXPIRED
