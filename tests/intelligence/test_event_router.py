from datetime import datetime

from backend.intelligence.global_intelligence.event_models import (
    EventCategory,
    EventSeverity,
    IntelligenceEvent,
)
from backend.intelligence.global_intelligence.intelligence_event_router import IntelligenceEventRouter
from backend.intelligence.global_intelligence.intelligence_state_manager import IntelligenceStateManager


class StubPersistence:
    def __init__(self) -> None:
        self.saved = []
        self.archived = 0

    def save_event(self, event: IntelligenceEvent) -> bool:
        self.saved.append(event.event_id)
        return True

    def archive_expired_events(self) -> int:
        self.archived += 1
        return self.archived


class StubHealthMonitor:
    def get_health_snapshot(self, events, ingestion_errors=0):
        return {"status": "HEALTHY", "issues": []}


def test_route_classified_event_and_persistence():
    state_manager = IntelligenceStateManager()
    persistence = StubPersistence()
    router = IntelligenceEventRouter(persistence_engine=persistence)
    event = IntelligenceEvent(
        event_id="router-1",
        timestamp=datetime.utcnow(),
        title="Router test event",
        category=EventCategory.GEOPOLITICAL,
        severity=EventSeverity.LOW,
        confidence=55.0,
        source="unit-test",
        affected_assets=["FX"],
        description="Routing event.",
    )

    result = router.route_classified_event(event, state_manager=state_manager)
    assert result is event
    assert state_manager.get_active_events()[0].event_id == "router-1"
    assert persistence.saved == ["router-1"]


def test_route_dashboard_payload_safe():
    router = IntelligenceEventRouter()
    state_manager = IntelligenceStateManager()
    payload = router.route_dashboard_payload(state_manager)
    assert isinstance(payload, dict)
    assert payload.get("dashboard_safe") is True


def test_route_health_snapshot():
    router = IntelligenceEventRouter(health_monitor=StubHealthMonitor())
    snapshot = router.route_health_snapshot([], ingestion_errors=2)
    assert snapshot["status"] == "HEALTHY"
    assert snapshot["issues"] == []
