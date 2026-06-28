"""
Runtime Statistics for CSS Operations Control Centre

Aggregates in-memory performance gauges and metrics counters.
Thread-safe.
"""

import threading
from typing import Dict, Any

class RuntimeStatistics:
    """
    Tracks runtime throughput, error counts, and system metrics.
    
    Responsibility: Maintain volatile gauges (e.g. CPU load, Memory, processing rate) and execution counters.
    Dependencies: None.
    Thread-safety: Fully synchronized via threading.Lock.
    Integration: Updated by various execution pathways and read by OperationsService.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._counters: Dict[str, int] = {}
        self._gauges: Dict[str, float] = {}

    def increment(self, metric: str, amount: int = 1) -> None:
        """Increment a counter metric."""
        with self._lock:
            self._counters[metric] = self._counters.get(metric, 0) + amount

    def set_gauge(self, metric: str, value: float) -> None:
        """Set the current float value of a gauge metric."""
        with self._lock:
            self._gauges[metric] = value

    def get_summary(self) -> Dict[str, Any]:
        """Retrieve copy of all stats counters and gauges."""
        with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges)
            }

    def reset(self) -> None:
        """Reset all tracked metrics to default/empty state."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
