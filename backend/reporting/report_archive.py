"""
Report Archive for CSS Reporting Framework

Archives report Events individually.
Exposes standard persistence APIs: save(), load(), append(), clear().
Thread-safe.
"""

import glob
import os
import threading
from typing import List
from backend.events.event_models import Event
from backend.common.persistence import save_json, load_json
from backend.common.exceptions import PersistenceException

class ReportArchive:
    """
    Manages individual report files inside the report archive directory.
    
    Responsibility: Persist individual generated report files to prevent loss.
    Dependencies: backend.events.event_models.Event, backend.common.persistence
    Thread-safety: Fully synchronized via threading.RLock.
    Integration: Accessed by ReportingService during report creation.
    """
    def __init__(self, archive_dir: str = "artifacts/reports/"):
        self.archive_dir = os.path.abspath(archive_dir)
        self._lock = threading.RLock()

    def load(self) -> List[Event]:
        """
        Load all archived reports from disk.
        """
        events = []
        with self._lock:
            if not os.path.exists(self.archive_dir):
                return []
            pattern = os.path.join(self.archive_dir, "report_*.json")
            files = glob.glob(pattern)
            for fpath in files:
                try:
                    data = load_json(fpath, self._lock)
                    events.append(Event.from_dict(data))
                except Exception:
                    continue
        return events

    def save(self, events: List[Event]) -> None:
        """
        Overwrite the archive with the provided list of report events.
        """
        self.clear()
        for e in events:
            self.append(e)

    def append(self, event: Event) -> None:
        """
        Archive a single report Event to report_{event_id}.json.
        """
        try:
            fpath = os.path.join(self.archive_dir, f"report_{event.event_id}.json")
            save_json(fpath, event.to_dict(), self._lock)
        except Exception as e:
            raise PersistenceException(f"Failed to archive report: {e}")

    def clear(self) -> None:
        """
        Delete all report files in the archive.
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
