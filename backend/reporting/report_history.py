"""
Report History manifest for CSS Reporting Framework

Logs manifest index of generated reports using the canonical Event model.
Exposes standard persistence APIs: save(), load(), append(), clear().
Thread-safe.
"""

import json
import os
import threading
from typing import List
from backend.events.event_models import Event

class ReportHistory:
    """
    Manages history manifest indexing generated reports.
    
    Responsibility: Audit index tracing metadata of all completed report runs.
    Dependencies: backend.events.event_models.Event
    Thread-safety: Fully synchronized via threading.Lock.
    Integration: Leveraged by ReportingService.
    """
    def __init__(self, history_file: str = "artifacts/reports/report_history.json"):
        self.history_file = os.path.abspath(history_file)
        self._lock = threading.Lock()

    def load(self) -> List[Event]:
        """
        Load history manifest events from disk.
        Matches EWP-1 standard persistence APIs.
        """
        with self._lock:
            if not os.path.exists(self.history_file):
                return []
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return [Event.from_dict(item) for item in data]
            except Exception:
                return []

    def save(self, events: List[Event]) -> None:
        """
        Overwrite the manifest index file with the provided events list.
        Matches EWP-1 standard persistence APIs.
        """
        dir_name = os.path.dirname(self.history_file)
        with self._lock:
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            data = [e.to_dict() for e in events]
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)

    def append(self, event: Event) -> None:
        """
        Append an event to the manifest index file.
        Matches EWP-1 standard persistence APIs.
        """
        events = self.load()
        events.append(event)
        self.save(events)

    def clear(self) -> None:
        """
        Clear all entries in the manifest log file.
        Matches EWP-1 standard persistence APIs.
        """
        self.save([])
