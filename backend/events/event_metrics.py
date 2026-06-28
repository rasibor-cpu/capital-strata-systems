"""
Event Metrics for CSS Enterprise Event Bus

Tracks publish, persist, and delivery metrics.
"""

import threading
from typing import Dict, Any
from backend.events.event_models import Event

class EventMetrics:
    def __init__(self):
        self._lock = threading.Lock()
        self.total_published: int = 0
        self.total_persisted: int = 0
        self.total_failed_deliveries: int = 0
        self.events_by_category: Dict[str, int] = {}
        self.events_by_severity: Dict[str, int] = {}

    def record_publish(self, event: Event) -> None:
        """Record details of a published event."""
        with self._lock:
            self.total_published += 1
            self.events_by_category[event.category] = self.events_by_category.get(event.category, 0) + 1
            self.events_by_severity[event.severity] = self.events_by_severity.get(event.severity, 0) + 1

    def record_persist(self, event: Event) -> None:
        """Record successful persistence of an event."""
        with self._lock:
            self.total_persisted += 1

    def record_delivery_failure(self) -> None:
        """Record exception/failure in subscriber execution."""
        with self._lock:
            self.total_failed_deliveries += 1

    def get_summary(self) -> Dict[str, Any]:
        """Return a copy of the current metrics summary."""
        with self._lock:
            return {
                "total_published": self.total_published,
                "total_persisted": self.total_persisted,
                "total_failed_deliveries": self.total_failed_deliveries,
                "events_by_category": dict(self.events_by_category),
                "events_by_severity": dict(self.events_by_severity)
            }

    def reset(self) -> None:
        """Reset all metrics back to default/zero."""
        with self._lock:
            self.total_published = 0
            self.total_persisted = 0
            self.total_failed_deliveries = 0
            self.events_by_category.clear()
            self.events_by_severity.clear()
