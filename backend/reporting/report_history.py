"""
Report History manifest for CSS Reporting Framework

Logs manifest index of generated reports using the canonical Event model.
Exposes standard persistence APIs: save(), load(), append(), clear().
Thread-safe.
"""

import os
import threading
from typing import List
from backend.events.event_models import Event
from backend.common.persistence import save_json, load_json
from backend.common.exceptions import PersistenceException

class ReportHistory:
    """
    Manages history manifest indexing generated reports.
    
    Responsibility: Audit index tracing metadata of all completed report runs.
    Dependencies: backend.events.event_models.Event, backend.common.persistence
    Thread-safety: Fully synchronized via threading.RLock.
    Integration: Leveraged by ReportingService.
    """
    def __init__(self, history_file: str = "artifacts/reports/report_history.json"):
        self.history_file = os.path.abspath(history_file)
        self._lock = threading.RLock()

    def load(self) -> List[Event]:
        """
        Load history manifest events from disk.
        """
        try:
            data = load_json(self.history_file, self._lock)
            if not isinstance(data, list):
                return []
            return [Event.from_dict(item) for item in data]
        except Exception as e:
            raise PersistenceException(f"Failed to load report history manifest: {e}")

    def save(self, events: List[Event]) -> None:
        """
        Overwrite the manifest index file with the provided events list.
        """
        try:
            data = [e.to_dict() for e in events]
            save_json(self.history_file, data, self._lock)
        except Exception as e:
            raise PersistenceException(f"Failed to save report history manifest: {e}")

    def append(self, event: Event) -> None:
        """
        Append an event to the manifest index file.
        """
        with self._lock:
            events = self.load()
            events.append(event)
            self.save(events)

    def clear(self) -> None:
        """
        Clear all entries in the manifest log file.
        """
        self.save([])
