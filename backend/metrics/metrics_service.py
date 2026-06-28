"""
Metrics Service Coordinator for CSS Observability Subsystem

Implements the primary service API for Metrics, Telemetry, and Health.
"""

import time
import logging
from typing import Optional, List, Dict, Any
from backend.events.event_models import Event
from backend.metrics.metrics_snapshot import MetricsSnapshot
from backend.metrics.metrics_registry import MetricsRegistry
from backend.metrics.telemetry import TelemetryCollector
from backend.metrics.health_metrics import HealthEvaluator
from backend.metrics.metrics_history import MetricsHistory

logger = logging.getLogger("css.metrics.service")

class MetricsService:
    """
    Observability coordinator class.
    
    Responsibility: Listen to Event Bus wildcard to record telemetry, metrics, and health states.
    Thread-safety: Synchronized via internal locks in components.
    """
    def __init__(
        self,
        registry: Optional[MetricsRegistry] = None,
        telemetry: Optional[TelemetryCollector] = None,
        history: Optional[MetricsHistory] = None
    ):
        self.registry = registry or MetricsRegistry()
        self.telemetry = telemetry or TelemetryCollector()
        self.history = history or MetricsHistory()

    def handle_event(self, event: Event) -> None:
        """Passive Event Bus wildcard subscriber callback."""
        try:
            # 1. System telemetry
            self.registry.increment("events_published")
            latency_ms = (time.time() - event.timestamp) * 1000.0
            self.telemetry.record_latency(latency_ms)

            # 2. Specific Event type routing
            etype = event.event_type
            if etype == "RUNTIME_STARTED":
                self.registry.increment("runtime_starts")
            elif etype == "RUNTIME_STOPPED":
                self.registry.increment("runtime_stops")
            elif etype == "RECOVERY_STARTED":
                pass
            elif etype == "RECOVERY_COMPLETE":
                self.registry.increment("recovery_count")
                dur = event.payload.get("delay_seconds", 0.0)
                self.telemetry.record_recovery_duration(dur)
            elif etype == "HEARTBEAT":
                self.telemetry.record_heartbeat()
            elif etype == "TRADE_APPROVED":
                self.registry.increment("trades_approved")
            elif etype == "TRADE_REJECTED":
                self.registry.increment("trades_rejected")
            elif etype == "ORDER_SUBMITTED":
                self.registry.increment("orders_submitted")
            elif etype == "ORDER_FILLED":
                self.registry.increment("orders_filled")
            elif etype == "NOTIFICATION_DISPATCH":
                status = event.payload.get("delivery_status", "PENDING")
                if status == "PENDING":
                    self.registry.increment("notifications_queued")
                elif status == "SENT":
                    self.registry.increment("notifications_delivered")
                elif "FAILED" in status:
                    self.registry.increment("notifications_failed")
            elif etype == "REPORT_GENERATED":
                self.registry.increment("reports_generated")
            elif etype == "REPORT_QUEUED":
                self.registry.increment("reports_queued")
            elif etype == "DELIVERY_FAILURE":
                self.registry.increment("subscriber_failures")
        except Exception as e:
            logger.error(f"Error in MetricsService handle_event: {e}")

    def record_subscriber_failure(self) -> None:
        """Call on delivery failures or subscriber exceptions."""
        self.registry.increment("subscriber_failures")

    def compile_snapshot(self) -> MetricsSnapshot:
        """Compile current metrics, telemetry, and health states into MetricsSnapshot."""
        metrics_all = self.registry.get_all()
        telemetry_all = self.telemetry.compile_telemetry(metrics_all["events_published"])
        
        # Evaluate health
        health_all = HealthEvaluator.calculate_health(
            restart_count=metrics_all["recovery_count"],
            heartbeat_age=telemetry_all["heartbeat_age_seconds"],
            notif_delivered=metrics_all["notifications_delivered"],
            notif_failed=metrics_all["notifications_failed"],
            report_backlog=telemetry_all["reporting_backlog"],
            subscriber_failures=metrics_all["subscriber_failures"]
        )

        return MetricsSnapshot(
            timestamp=time.time(),
            metrics=metrics_all,
            telemetry=telemetry_all,
            health=health_all
        )

    def persist_snapshot(self) -> MetricsSnapshot:
        """Compile and append snapshot to history log."""
        snapshot = self.compile_snapshot()
        self.history.append(snapshot)
        return snapshot

    def get_latest_snapshot(self) -> MetricsSnapshot:
        """Get current compiled snapshot."""
        return self.compile_snapshot()

    def get_recent_snapshots(self, limit: int = 50) -> List[MetricsSnapshot]:
        """Fetch historical snapshots from disk."""
        return self.history.load()[-limit:]

    def get_current_health(self) -> Dict[str, Any]:
        """Expose health component scores."""
        return self.compile_snapshot().health

    def get_current_metrics(self) -> Dict[str, int]:
        """Expose current metrics counter values."""
        return self.registry.get_all()

    def get_telemetry_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Expose historical telemetry records."""
        snapshots = self.get_recent_snapshots(limit)
        return [s.telemetry for s in snapshots]
