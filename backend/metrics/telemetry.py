"""
Telemetry Collector for CSS Observability Subsystem

Tracks time-series measurements: latencies, throughputs, and queue depths.
"""

import threading
import time
from typing import Dict, Any

class TelemetryCollector:
    """
    Tracks operational time-series telemetries under a thread lock.
    
    Responsibility: Gather throughput and latency aggregates.
    """
    def __init__(self):
        self._lock = threading.RLock()
        self.start_time = time.time()
        self.last_heartbeat_time = time.time()
        self.total_latency_ms = 0.0
        self.latency_count = 0
        
        # Volatile backing queues depths
        self.notification_queue_depth = 0
        self.reporting_backlog = 0
        self.recovery_duration = 0.0

    def record_heartbeat(self) -> None:
        """Update last heartbeat timestamp."""
        with self._lock:
            self.last_heartbeat_time = time.time()

    def record_latency(self, latency_ms: float) -> None:
        """Accumulate publish latency measurement."""
        with self._lock:
            if latency_ms >= 0:
                self.total_latency_ms += latency_ms
                self.latency_count += 1

    def record_queues(self, notif_depth: int, report_backlog: int) -> None:
        """Update current queue depths."""
        with self._lock:
            self.notification_queue_depth = notif_depth
            self.reporting_backlog = report_backlog

    def record_recovery_duration(self, duration: float) -> None:
        """Record service recovery duration."""
        with self._lock:
            self.recovery_duration = duration

    def compile_telemetry(self, event_count: int) -> Dict[str, Any]:
        """Compile a telemetry dict snapshot using current indicators."""
        with self._lock:
            now = time.time()
            uptime = now - self.start_time
            heartbeat_age = now - self.last_heartbeat_time
            
            avg_latency = 0.0
            if self.latency_count > 0:
                avg_latency = self.total_latency_ms / self.latency_count
                
            throughput = 0.0
            if uptime > 0:
                throughput = event_count / uptime
                
            return {
                "event_throughput_per_sec": throughput,
                "publish_latency_avg_ms": avg_latency,
                "notification_queue_depth": self.notification_queue_depth,
                "reporting_backlog": self.reporting_backlog,
                "heartbeat_age_seconds": heartbeat_age,
                "runtime_uptime_seconds": uptime,
                "recovery_duration_seconds": self.recovery_duration
            }
