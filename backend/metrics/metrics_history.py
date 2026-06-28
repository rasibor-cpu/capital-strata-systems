"""
Metrics History for CSS Observability Subsystem

Logs snapshot aggregates persistently using shared JSON operations.
"""

import threading
from typing import List, Dict, Any
from backend.metrics.metrics_snapshot import MetricsSnapshot
from backend.common.persistence import load_json, save_json
from backend.common.exceptions import PersistenceException

class MetricsHistory:
    """
    Manages long-term storage of metric snapshots.
    
    Responsibility: Persist consolidated snapshots thread-safely.
    """
    def __init__(self, file_path: str = "artifacts/metrics/metrics_snapshots.json"):
        self.file_path = file_path
        self._lock = threading.RLock()

    def load(self) -> List[MetricsSnapshot]:
        """Load all historically logged snapshots from disk."""
        try:
            data = load_json(self.file_path, self._lock)
            if not isinstance(data, list):
                return []
            return [MetricsSnapshot.from_dict(item) for item in data]
        except Exception as e:
            raise PersistenceException(f"Failed to load metrics history: {e}")

    def save(self, snapshots: List[MetricsSnapshot]) -> None:
        """Overwrite metrics history log on disk."""
        try:
            data = [s.to_dict() for s in snapshots]
            save_json(self.file_path, data, self._lock)
        except Exception as e:
            raise PersistenceException(f"Failed to save metrics history: {e}")

    def append(self, snapshot: MetricsSnapshot) -> None:
        """Append a snapshot to the history log."""
        with self._lock:
            snapshots = self.load()
            snapshots.append(snapshot)
            self.save(snapshots)

    def clear(self) -> None:
        """Clear all metrics snapshots."""
        self.save([])
