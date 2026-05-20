from datetime import datetime, timedelta

from backend.intelligence.global_intelligence.dashboard_intelligence_widgets import build_dashboard_widgets
from backend.intelligence.global_intelligence.event_models import (
    EventCategory,
    EventSeverity,
    IntelligenceEvent,
)
from backend.intelligence.global_intelligence.intelligence_state_manager import IntelligenceStateManager


def test_build_dashboard_widgets_with_state():
    state_manager = IntelligenceStateManager()
    event = IntelligenceEvent(
        event_id="dashboard-1",
        timestamp=datetime.utcnow() - timedelta(hours=1),
        title="Dashboard test event",
        category=EventCategory.GEOPOLITICAL,
        severity=EventSeverity.HIGH,
        confidence=85.0,
        source="unit-test",
        affected_assets=["FX"],
        description="Testing widget payload.",
    )
    state_manager.add_event(event)
    payload = build_dashboard_widgets(state_manager)

    assert payload["dashboard_safe"] is True
    assert payload["event_count"] == 1
    assert payload["global_risk_meter"] in {"NORMAL", "CAUTION", "DEFENSIVE", "PANIC"}
    assert isinstance(payload["active_event_feed"], list)
    assert isinstance(payload["governance_status"], dict)


def test_build_dashboard_widgets_failure_safe():
    payload = build_dashboard_widgets(None)
    assert payload["dashboard_safe"] is True
    assert payload["event_count"] == 0
    assert payload["global_risk_meter"] == "NORMAL"
