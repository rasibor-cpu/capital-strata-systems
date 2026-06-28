"""
Operational Timeline for CSS Operations Control Centre

Maintains chronological log of timeline Event objects.
Exposes standard persistence APIs: save(), load(), append(), clear().
Thread-safe.
"""

import json
import os
import threading
from typing import List
from backend.events.event_models import Event

class OperationalTimeline:
    """
    Manages persistent chronological logs of operational timeline Events.
    
    Responsibility: Persist chronological log updates for operational diagnostics.
    Dependencies: backend.events.event_models.Event
    Thread-safety: Fully synchronized via threading.Lock.
    Integration: Accessed by OperationsService.
    """
    def __init__(self, file_path: str = "artifacts/operations/operational_timeline.json"):
        self.file_path = os.path.abspath(file_path)
        self._lock = threading.Lock()

    def load(self) -> List[Event]:
        """
        Load all timeline events from disk.
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
        Overwrite timeline log with provided events list.
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
        Append a timeline event to the log file.
        Matches EWP-1 standard persistence APIs.
        """
        events = self.load()
        events.append(event)
        self.save(events)

    def clear(self) -> None:
        """
        Clear all events in the timeline log file.
        Matches EWP-1 standard persistence APIs.
        """
        self.save([])
