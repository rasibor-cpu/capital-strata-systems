"""
Operational State Manager for CSS Operations Control Centre

Tracks and persists the system health snapshot state as a canonical Event.
Exposes standard persistence APIs: save(), load(), append(), clear().
Thread-safe.
"""

import json
import os
import threading
from typing import List, Optional
from backend.events.event_models import Event

class OperationalStateManager:
    """
    Manages current system health state, persisting to operational_state.json.
    
    Responsibility: Persist overall system status to represent running state.
    Dependencies: backend.events.event_models.Event
    Thread-safety: Fully synchronized via threading.Lock.
    Integration: Accessed by OperationsService.
    """
    def __init__(self, file_path: str = "artifacts/operations/operational_state.json"):
        self.file_path = os.path.abspath(file_path)
        self._lock = threading.Lock()

    def load(self) -> List[Event]:
        """
        Load current state event snapshot from disk.
        Matches EWP-1 standard persistence APIs.
        """
        with self._lock:
            if not os.path.exists(self.file_path):
                return []
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return [Event.from_dict(data)]
            except Exception:
                return []

    def save(self, events: List[Event]) -> None:
        """
        Overwrite system state with the provided event list (uses first event).
        Matches EWP-1 standard persistence APIs.
        """
        dir_name = os.path.dirname(self.file_path)
        with self._lock:
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            if not events:
                if os.path.exists(self.file_path):
                    try:
                        os.remove(self.file_path)
                    except Exception:
                        pass
                return
            data = events[0].to_dict()
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)

    def append(self, event: Event) -> None:
        """
        Append / overwrite state with the latest event snapshot.
        Matches EWP-1 standard persistence APIs.
        """
        self.save([event])

    def clear(self) -> None:
        """
        Delete the state snapshot file.
        Matches EWP-1 standard persistence APIs.
        """
        self.save([])
