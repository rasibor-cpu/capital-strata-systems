"""
CSS Event Visibility Layer

Exposes passive read-model functions for dashboards and alert centres
by querying persisted JSON/JSONL logs directly.
"""

import threading
from typing import List, Dict, Any
from backend.events.event_models import Event
from backend.common.persistence import load_json, load_jsonl

class EventVisibilityLayer:
    """
    Read-model service for dashboards and alert centres.
    Reads persistent files directly without modifying running state.
    
    Responsibility: Query recent events, notifications history, and system status details.
    Dependencies: backend.common.persistence
    Thread-safety: Fully thread-safe, uses internal lock.
    """
    def __init__(
        self,
        event_store_file: str = "artifacts/events/css_events.jsonl",
        notification_queue_file: str = "artifacts/notifications/css_notification_queue.json",
        notification_history_file: str = "artifacts/notifications/css_notification_history.json",
        operational_state_file: str = "artifacts/operations/operational_state.json",
        operational_timeline_file: str = "artifacts/operations/operational_timeline.json"
    ):
        self.event_store_file = event_store_file
        self.notification_queue_file = notification_queue_file
        self.notification_history_file = notification_history_file
        self.operational_state_file = operational_state_file
        self.operational_timeline_file = operational_timeline_file
        self._lock = threading.RLock()

    def get_recent_events(self, limit: int = 50) -> List[Event]:
        """Expose list of recent enterprise events from event store."""
        try:
            dicts = load_jsonl(self.event_store_file, self._lock)
            events = [Event.from_dict(d) for d in dicts]
            return events[-limit:]
        except Exception:
            return []

    def get_recent_notifications(self, limit: int = 50) -> List[Event]:
        """Expose recent notification events logged in history."""
        try:
            dicts = load_json(self.notification_history_file, self._lock)
            events = [Event.from_dict(d) for d in dicts]
            return events[-limit:]
        except Exception:
            return []

    def get_recent_timeline_events(self, limit: int = 50) -> List[Event]:
        """Expose recent operational timeline events."""
        try:
            dicts = load_json(self.operational_timeline_file, self._lock)
            events = [Event.from_dict(d) for d in dicts]
            return events[-limit:]
        except Exception:
            return []

    def get_notification_summary(self) -> Dict[str, Any]:
        """Expose summary of pending queue counts and history statistics."""
        try:
            queue_data = load_json(self.notification_queue_file, self._lock)
            queue_count = len(queue_data) if isinstance(queue_data, list) else 0

            history_data = load_json(self.notification_history_file, self._lock)
            history_events = [Event.from_dict(h) for h in history_data] if isinstance(history_data, list) else []

            counts = {"SENT": 0, "FAILED": 0, "FILTERED": 0}
            for e in history_events:
                status = e.payload.get("delivery_status", "UNKNOWN")
                if "FAILED" in status:
                    counts["FAILED"] += 1
                elif "FILTERED" in status:
                    counts["FILTERED"] += 1
                elif status == "SENT":
                    counts["SENT"] += 1

            return {
                "queue_count": queue_count,
                "sent_count": counts["SENT"],
                "failed_count": counts["FAILED"],
                "filtered_count": counts["FILTERED"],
                "total_history_count": len(history_events)
            }
        except Exception:
            return {
                "queue_count": 0,
                "sent_count": 0,
                "failed_count": 0,
                "filtered_count": 0,
                "total_history_count": 0
            }

    def get_operations_summary(self) -> Dict[str, Any]:
        """Expose summary of system health state and recent transition details."""
        try:
            state_data = load_json(self.operational_state_file, self._lock)
            overall_status = "UNKNOWN"
            health_score = 0.0
            components = {}
            if isinstance(state_data, dict) and "payload" in state_data:
                payload = state_data["payload"]
                overall_status = payload.get("overall_status", "UNKNOWN")
                health_score = payload.get("health_score", 0.0)
                components = payload.get("component_states", {})

            timeline_data = load_json(self.operational_timeline_file, self._lock)
            timeline_len = len(timeline_data) if isinstance(timeline_data, list) else 0

            return {
                "overall_status": overall_status,
                "health_score": health_score,
                "component_states": components,
                "timeline_length": timeline_len
            }
        except Exception:
            return {
                "overall_status": "UNKNOWN",
                "health_score": 0.0,
                "component_states": {},
                "timeline_length": 0
            }
