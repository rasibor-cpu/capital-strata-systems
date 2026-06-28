"""
Operational Timeline for CSS Operations Control Centre

Maintains chronological log of timeline Event objects.
Exposes standard persistence APIs: save(), load(), append(), clear().
Thread-safe.
"""

import threading
from typing import List
from backend.events.event_models import Event
from backend.common.persistence import save_json, load_json
from backend.common.exceptions import PersistenceException

class OperationalTimeline:
    """
    Manages persistent chronological logs of operational timeline Events.
    
    Responsibility: Persist chronological log updates for operational diagnostics.
    Dependencies: backend.events.event_models.Event, backend.common.persistence
    Thread-safety: Fully synchronized via threading.RLock.
    Integration: Accessed by OperationsService.
    """
    def __init__(self, file_path: str = "artifacts/operations/operational_timeline.json"):
        self.file_path = file_path
        self._lock = threading.RLock()

    def load(self) -> List[Event]:
        """
        Load all timeline events from disk.
        """
        try:
            data = load_json(self.file_path, self._lock)
            if not isinstance(data, list):
                return []
            return [Event.from_dict(item) for item in data]
        except Exception as e:
            raise PersistenceException(f"Failed to load operational timeline: {e}")

    def save(self, events: List[Event]) -> None:
        """
        Overwrite timeline log with provided events list.
        """
        try:
            data = [e.to_dict() for e in events]
            save_json(self.file_path, data, self._lock)
        except Exception as e:
            raise PersistenceException(f"Failed to save operational timeline: {e}")

    def append(self, event: Event) -> None:
        """
        Append a timeline event to the log file.
        """
        with self._lock:
            events = self.load()
            events.append(event)
            self.save(events)

    def clear(self) -> None:
        """
        Clear all events in the timeline log file.
        """
        self.save([])
