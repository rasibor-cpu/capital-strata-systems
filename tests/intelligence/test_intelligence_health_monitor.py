from datetime import datetime, timedelta

from backend.intelligence.global_intelligence.event_models import (
    EventCategory,
    EventSeverity,
    IntelligenceEvent,
)
from backend.intelligence.global_intelligence.intelligence_health_monitor import IntelligenceHealthMonitor


def test_health_snapshot_reports_issues_for_invalid_event():
    monitor = IntelligenceHealthMonitor()
    now = datetime.utcnow()
    event = IntelligenceEvent(
        event_id="health-1",
        timestamp=now - timedelta(days=4),
        title="Stale event",
        category=EventCategory.GEOPOLITICAL,
        severity=EventSeverity.HIGH,
        confidence=150.0,
        source="unit-test",
        affected_assets=["FX"],
        description="Confidence out of bounds.",
    )

    snapshot = monitor.get_health_snapshot([event], ingestion_errors=1, now=now)
    assert snapshot["event_count"] == 1
    assert "invalid_confidence" in snapshot["issues"]
    assert "stale_event" in snapshot["issues"]
    assert snapshot["status"] in {"DEGRADED", "CRITICAL", "WARNING"}
