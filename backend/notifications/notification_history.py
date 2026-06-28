"""
Notification History for CSS Notification Framework

Logs delivery attempts and final states using the canonical Event model.
Exposes standard persistence APIs: save(), load(), append(), clear().
Thread-safe.
"""

import threading
from typing import List
from backend.events.event_models import Event
from backend.common.persistence import save_json, load_json
from backend.common.exceptions import PersistenceException

class NotificationHistory:
    """
    Manages long-term delivery tracking logs of events.
    
    Responsibility: Audit log of all sent, failed, or filtered notifications.
    Dependencies: backend.events.event_models.Event, backend.common.persistence
    Thread-safety: Fully synchronized via threading.RLock.
    Integration: Read by operations dashboards or support teams to trace message alerts.
    """
    def __init__(self, file_path: str = "artifacts/notifications/css_notification_history.json"):
        self.file_path = file_path
        self._lock = threading.RLock()

    def load(self) -> List[Event]:
        """
        Load all historically logged notification events from disk.
        """
        try:
            data = load_json(self.file_path, self._lock)
            if not isinstance(data, list):
                return []
            return [Event.from_dict(item) for item in data]
        except Exception as e:
            raise PersistenceException(f"Failed to load notification history: {e}")

    def save(self, events: List[Event]) -> None:
        """
        Save a list of events to history, overwriting existing content.
        """
        try:
            data = [e.to_dict() for e in events]
            save_json(self.file_path, data, self._lock)
        except Exception as e:
            raise PersistenceException(f"Failed to save notification history: {e}")

    def append(self, event: Event) -> None:
        """
        Append an event to the history log.
        """
        with self._lock:
            events = self.load()
            events.append(event)
            self.save(events)

    def clear(self) -> None:
        """
        Clear all events in history.
        """
        self.save([])
