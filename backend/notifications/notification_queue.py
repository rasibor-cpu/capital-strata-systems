"""
Notification Queue for CSS Notification Framework

Persists pending notifications using the canonical Event model.
Exposes standard persistence APIs: save(), load(), append(), clear().
Thread-safe.
"""

import json
import os
import threading
from typing import List, Optional
from backend.events.event_models import Event

class NotificationQueue:
    """
    Handles file-backed FIFO queueing of notification events.
    
    Responsibility: Persist pending notifications to prevent loss during runtime interruption.
    Dependencies: backend.events.event_models.Event
    Thread-safety: Fully synchronized via threading.Lock.
    Integration: Accessed by NotificationService to queue and retry notifications.
    """
    def __init__(self, file_path: str = "artifacts/notifications/css_notification_queue.json"):
        self.file_path = os.path.abspath(file_path)
        self._lock = threading.Lock()

    def load(self) -> List[Event]:
        """
        Load all queued notification events from disk.
        Matches EWP-1 standard persistence APIs.
        """
        with self._lock:
            if not os.path.exists(self.file_path):
                return []
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return [Event.from_dict(item) for item in data]
            except Exception:
                return []

    def save(self, events: List[Event]) -> None:
        """
        Save a list of events to the queue, overwriting existing content.
        Matches EWP-1 standard persistence APIs.
        """
        dir_name = os.path.dirname(self.file_path)
        with self._lock:
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            data = [e.to_dict() for e in events]
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)

    def append(self, event: Event) -> None:
        """
        Append an event to the queue.
        Matches EWP-1 standard persistence APIs.
        """
        events = self.load()
        events.append(event)
        self.save(events)

    def clear(self) -> None:
        """
        Clear all events in the queue.
        Matches EWP-1 standard persistence APIs.
        """
        self.save([])

    def dequeue(self) -> Optional[Event]:
        """Pop the first event from the queue in a thread-safe manner."""
        with self._lock:
            if not os.path.exists(self.file_path):
                return None
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    events = [Event.from_dict(item) for item in data]
            except Exception:
                events = []
            
            if not events:
                return None
            
            next_event = events.pop(0)
            
            dir_name = os.path.dirname(self.file_path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            data = [e.to_dict() for e in events]
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
                
            return next_event
