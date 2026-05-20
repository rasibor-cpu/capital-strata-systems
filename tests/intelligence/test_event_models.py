from datetime import datetime, timezone

from backend.intelligence.global_intelligence.event_models import (
    EventCategory,
    EventSeverity,
    GovernanceResponse,
    IntelligenceEvent,
    RegimeState,
)


def test_event_models_clamp_and_enums():
    event = IntelligenceEvent(
        event_id="evt-1",
        timestamp=datetime.now(timezone.utc),
        title="Test Event",
        category=EventCategory.UNKNOWN,
        severity=EventSeverity.CRITICAL,
        confidence=150,
        source="Unknown Source",
        affected_assets=None,
    )

    assert event.confidence == 100.0
    assert event.affected_assets == []
    assert EventSeverity.LOW.value < EventSeverity.CRITICAL.value
    assert RegimeState.PANIC.value == "PANIC"


def test_governance_response_clamping():
    response = GovernanceResponse(reduce_allocation_pct=120, leverage_multiplier=-1, notes=None)
    assert response.reduce_allocation_pct == 100.0
    assert response.leverage_multiplier == 0.0
    assert response.notes == []
