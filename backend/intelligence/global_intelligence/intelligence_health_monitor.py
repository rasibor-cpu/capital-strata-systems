from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable

from .event_models import IntelligenceEvent


class IntelligenceHealthMonitor:
    MAX_ACTIVE_EVENTS = 20
    STALE_EVENT_THRESHOLD = timedelta(days=3)

    def get_health_snapshot(
        self,
        events: Iterable[IntelligenceEvent] | None = None,
        ingestion_errors: int = 0,
        now: datetime | None = None,
    ) -> dict[str, object]:
        now = now or datetime.utcnow()
        events = list(events or [])
        issues: list[str] = []

        stale_count = 0
        invalid_confidence_count = 0
        for event in events:
            if event is None:
                continue
            confidence_value = getattr(event, "raw_confidence", event.confidence)
            if confidence_value < 0.0 or confidence_value > 100.0:
                invalid_confidence_count += 1
            if event.timestamp and now - event.timestamp > self.STALE_EVENT_THRESHOLD:
                stale_count += 1

        overflow = len(events) > self.MAX_ACTIVE_EVENTS
        if overflow:
            issues.append("event_overflow")
        if invalid_confidence_count:
            issues.append("invalid_confidence")
        if stale_count:
            issues.append("stale_event")
        if ingestion_errors:
            issues.append("failed_ingestion")

        status = "HEALTHY"
        if overflow or ingestion_errors > 5:
            status = "CRITICAL"
        elif invalid_confidence_count or stale_count:
            status = "DEGRADED"
        elif ingestion_errors > 0:
            status = "WARNING"

        return {
            "status": status,
            "event_count": len(events),
            "stale_events": stale_count,
            "invalid_confidence_events": invalid_confidence_count,
            "failed_ingestions": ingestion_errors,
            "issues": issues,
        }
