"""
Operational State Manager for CSS Operations Control Centre

Tracks and persists the system health snapshot state as a canonical Event.
Exposes standard persistence APIs: save(), load(), append(), clear().
Thread-safe.
"""

import threading
from typing import List
from backend.events.event_models import Event
from backend.common.persistence import save_json, load_json
from backend.common.exceptions import PersistenceException

class OperationalStateManager:
    """
    Manages current system health state, persisting to operational_state.json.
    
    Responsibility: Persist overall system status to represent running state.
    Dependencies: backend.events.event_models.Event, backend.common.persistence
    Thread-safety: Fully synchronized via threading.RLock.
    Integration: Accessed by OperationsService.
    """
    def __init__(self, file_path: str = "artifacts/operations/operational_state.json"):
        self.file_path = file_path
        self._lock = threading.RLock()

    def load(self) -> List[Event]:
        """
        Load current state event snapshot from disk.
        """
        try:
            data = load_json(self.file_path, self._lock)
            if not data or not isinstance(data, dict):
                return []
            return [Event.from_dict(data)]
        except Exception as e:
            raise PersistenceException(f"Failed to load operational state: {e}")

    def save(self, events: List[Event]) -> None:
        """
        Overwrite system state with the provided event list (uses first event).
        """
        try:
            if not events:
                save_json(self.file_path, {}, self._lock)
                return
            data = events[0].to_dict()
            save_json(self.file_path, data, self._lock)
        except Exception as e:
            raise PersistenceException(f"Failed to save operational state: {e}")

    def append(self, event: Event) -> None:
        """
        Append / overwrite state with the latest event snapshot.
        """
        self.save([event])

    def clear(self) -> None:
        """
        Delete/clear the state snapshot.
        """
        self.save([])
