"""
Notification Queue for CSS Notification Framework

Persists pending notifications using the canonical Event model.
Exposes standard persistence APIs: save(), load(), append(), clear().
Thread-safe.
"""

import threading
from typing import List, Optional
from backend.events.event_models import Event
from backend.common.persistence import save_json, load_json
from backend.common.exceptions import PersistenceException

class NotificationQueue:
    """
    Handles file-backed FIFO queueing of notification events.
    
    Responsibility: Persist pending notifications to prevent loss during runtime interruption.
    Dependencies: backend.events.event_models.Event, backend.common.persistence
    Thread-safety: Fully synchronized via threading.RLock.
    Integration: Accessed by NotificationService to queue and retry notifications.
    """
    def __init__(self, file_path: str = "artifacts/notifications/css_notification_queue.json"):
        self.file_path = file_path
        self._lock = threading.RLock()

    def load(self) -> List[Event]:
        """
        Load all queued notification events from disk.
        """
        try:
            data = load_json(self.file_path, self._lock)
            if not isinstance(data, list):
                return []
            return [Event.from_dict(item) for item in data]
        except Exception as e:
            raise PersistenceException(f"Failed to load notification queue: {e}")

    def save(self, events: List[Event]) -> None:
        """
        Save a list of events to the queue, overwriting existing content.
        """
        try:
            data = [e.to_dict() for e in events]
            save_json(self.file_path, data, self._lock)
        except Exception as e:
            raise PersistenceException(f"Failed to save notification queue: {e}")

    def append(self, event: Event) -> None:
        """
        Append an event to the queue.
        """
        with self._lock:
            events = self.load()
            events.append(event)
            self.save(events)

    def clear(self) -> None:
        """
        Clear all events in the queue.
        """
        self.save([])

    def dequeue(self) -> Optional[Event]:
        """Pop the first event from the queue in a thread-safe manner."""
        with self._lock:
            events = self.load()
            if not events:
                return None
            next_event = events.pop(0)
            self.save(events)
            return next_event
