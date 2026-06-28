"""
Report Archive for CSS Reporting Framework

Archives report Events individually.
Exposes standard persistence APIs: save(), load(), append(), clear().
Thread-safe.
"""

import glob
import json
import os
import threading
from typing import List, Optional
from backend.events.event_models import Event

class ReportArchive:
    """
    Manages individual report files inside the report archive directory.
    
    Responsibility: Persist individual generated report files to prevent loss.
    Dependencies: backend.events.event_models.Event
    Thread-safety: Fully synchronized via threading.Lock.
    Integration: Accessed by ReportingService during report creation.
    """
    def __init__(self, archive_dir: str = "artifacts/reports/"):
        self.archive_dir = os.path.abspath(archive_dir)
        self._lock = threading.Lock()

    def load(self) -> List[Event]:
        """
        Load all archived reports from disk.
        Matches EWP-1 standard persistence APIs.
        """
        events = []
        with self._lock:
            if not os.path.exists(self.archive_dir):
                return []
            pattern = os.path.join(self.archive_dir, "report_*.json")
            files = glob.glob(pattern)
            for fpath in files:
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        events.append(Event.from_dict(data))
                except Exception:
                    continue
        return events

    def save(self, events: List[Event]) -> None:
        """
        Overwrite the archive with the provided list of report events.
        Matches EWP-1 standard persistence APIs.
        """
        self.clear()
        for e in events:
            self.append(e)

    def append(self, event: Event) -> None:
        """
        Archive a single report Event to report_{event_id}.json.
        Matches EWP-1 standard persistence APIs.
        """
        with self._lock:
            os.makedirs(self.archive_dir, exist_ok=True)
            fpath = os.path.join(self.archive_dir, f"report_{event.event_id}.json")
            data = event.to_dict()
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)

    def clear(self) -> None:
        """
        Delete all report files in the archive.
        Matches EWP-1 standard persistence APIs.
        """
        with self._lock:
            if not os.path.exists(self.archive_dir):
                return
            pattern = os.path.join(self.archive_dir, "report_*.json")
            files = glob.glob(pattern)
            for fpath in files:
                try:
                    os.remove(fpath)
                except Exception:
                    continue
