"""
Dashboard Read Model for CSS Executive Operations Platform
"""

from typing import Dict, Any, List
import time
from backend.metrics.metrics_service import MetricsService
from backend.operations.operations_service import OperationsService
from backend.notifications.notification_service import NotificationService
from backend.reporting.reporting_service import ReportingService
from backend.events.visibility_layer import EventVisibilityLayer

class DashboardReadModel:
    """
    Read-only aggregator pulling telemetry details from active services.
    """
    def __init__(
        self,
        metrics_service: MetricsService,
        operations_service: OperationsService,
        notification_service: NotificationService,
        reporting_service: ReportingService,
        visibility_layer: EventVisibilityLayer
    ):
        self.metrics_service = metrics_service
        self.operations_service = operations_service
        self.notification_service = notification_service
        self.reporting_service = reporting_service
        self.visibility_layer = visibility_layer

    def get_enterprise_health(self) -> Dict[str, Any]:
        """Aggregate health state dictionary."""
        return self.metrics_service.get_current_health()

    def get_runtime_status(self) -> str:
        """Fetch current operational state overall status."""
        summary = self.visibility_layer.get_operations_summary()
        return summary.get("overall_status", "UNKNOWN")

    def get_engine_mode(self) -> str:
        """Derive active trading engine mode from recent events."""
        recent = self.visibility_layer.get_recent_events(limit=15)
        for e in reversed(recent):
            if isinstance(e.payload, dict) and "engine_mode" in e.payload:
                return str(e.payload["engine_mode"]).upper()
        return "CONSERVATIVE"

    def get_recent_events(self, limit: int = 50) -> List[Any]:
        """Fetch list of recent Event structures."""
        return self.visibility_layer.get_recent_events(limit=limit)

    def get_active_alerts(self) -> List[Any]:
        """Fetch list of active operational timeline warnings/errors."""
        timeline = self.visibility_layer.get_recent_timeline_events(limit=50)
        return [e for e in timeline if e.severity in ("WARNING", "CRITICAL")]

    def get_outstanding_notifications(self) -> List[Any]:
        """Fetch queued notifications."""
        return self.notification_service.queue.load()

    def get_report_status(self) -> Dict[str, Any]:
        """Fetch report logs summary."""
        history = self.reporting_service.history.load()
        return {
            "total_generated": len(history),
            "recent_reports": [
                {
                    "report_id": r.event_id,
                    "title": r.payload.get("title", "Untitled Report"),
                    "type": r.payload.get("report_type", "UNKNOWN"),
                    "timestamp": r.timestamp
                }
                for r in history[-10:]
            ]
        }
