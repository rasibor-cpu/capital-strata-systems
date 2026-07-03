from datetime import datetime, timedelta, timezone

from backend.intelligence.global_intelligence.event_models import (
    EventCategory,
    EventSeverity,
    IntelligenceEvent,
)
from backend.intelligence.global_intelligence.event_persistence_engine import EventPersistenceEngine


def test_save_and_load_recent_events(tmp_path):
    storage_file = tmp_path / "events.json"
    persistence = EventPersistenceEngine(storage_path=str(storage_file))
    event = IntelligenceEvent(
        event_id="test-event-1",
        timestamp=datetime.now(timezone.utc),
        title="Test event",
        category=EventCategory.GEOPOLITICAL,
        severity=EventSeverity.MODERATE,
        confidence=75.0,
        source="unit-test",
        affected_assets=["FX", "EQUITIES"],
        description="A test macro event.",
    )

    assert persistence.save_event(event) is True
    recent = persistence.load_recent_events(limit=5)
    assert isinstance(recent, list)
    assert recent and recent[-1]["event_id"] == "test-event-1"


def test_archive_expired_events(tmp_path):
    storage_file = tmp_path / "events.json"
    persistence = EventPersistenceEngine(storage_path=str(storage_file))
    expired_event = IntelligenceEvent(
        event_id="expired-event-1",
        timestamp=datetime.now(timezone.utc) - timedelta(days=2),
        title="Expired event",
        category=EventCategory.REGULATORY,
        severity=EventSeverity.LOW,
        confidence=50.0,
        source="unit-test",
        affected_assets=["BONDS"],
        description="This event is already expired.",
        active=False,
        expiration_time=datetime.now(timezone.utc) - timedelta(days=1),
    )

    persistence.save_event(expired_event)
    archived_count = persistence.archive_expired_events()
    assert archived_count >= 1
    assert len(persistence.load_recent_events()) == 0
