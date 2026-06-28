"""
Metrics Registry for CSS Observability Subsystem

Manages lock-synchronized counter accumulators.
"""

import threading
from typing import Dict

class MetricsRegistry:
    """
    Thread-safe storage of numerical counters.
    
    Responsibility: Safe concurrent metric updates.
    """
    def __init__(self):
        self._lock = threading.RLock()
        self._counters: Dict[str, int] = {
            "trades_approved": 0,
            "trades_rejected": 0,
            "runtime_starts": 0,
            "runtime_stops": 0,
            "recovery_count": 0,
            "notifications_queued": 0,
            "notifications_delivered": 0,
            "notifications_failed": 0,
            "reports_generated": 0,
            "reports_queued": 0,
            "events_published": 0,
            "events_persisted": 0,
            "subscriber_failures": 0
        }

    def increment(self, name: str, amount: int = 1) -> None:
        """Increment counter metric under lock."""
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + amount

    def set_val(self, name: str, val: int) -> None:
        """Set metric counter directly."""
        with self._lock:
            self._counters[name] = val

    def get_all(self) -> Dict[str, int]:
        """Get copy of all metrics."""
        with self._lock:
            return dict(self._counters)
