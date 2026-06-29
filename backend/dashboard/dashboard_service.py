"""
Dashboard Service Coordinator for CSS Executive Operations Platform
"""

import time
from typing import Dict, Any, List
from backend.dashboard.dashboard_read_model import DashboardReadModel
from backend.dashboard.executive_summary import ExecutiveSummaryBuilder

class DashboardService:
    """
    Main Service for Executive Operations Platform.
    Exposes read-only operational summaries, dashboard telemetry, and alert tracking.
    """
    def __init__(self, read_model: DashboardReadModel):
        self.read_model = read_model
        self.summary_builder = ExecutiveSummaryBuilder(read_model)

    def get_executive_summary(self) -> Dict[str, Any]:
        """Aggregate high-level summary overview indicators."""
        return self.summary_builder.build_summary()

    def get_operational_command_centre_view(self) -> Dict[str, Any]:
        """Expose command centre health indexes, recovery states, and statistics."""
        health = self.read_model.get_enterprise_health()
        timeline = self.read_model.get_recent_events(limit=30)
        
        return {
            "enterprise_health": health,
            "recent_critical_events": [
                {
                    "event_type": e.event_type,
                    "severity": e.severity,
                    "source": e.source,
                    "timestamp": e.timestamp,
                    "message": e.payload.get("message", f"{e.event_type} occurred")
                }
                for e in timeline if e.severity == "CRITICAL"
            ],
            "recovery_status": {
                "restart_count": health.get("restart_count", 0),
                "is_degraded": health.get("overall_health_score", 100.0) < 80.0
            },
            "operational_timeline": [
                {
                    "timestamp": e.timestamp,
                    "event_type": e.event_type,
                    "severity": e.severity,
                    "message": e.payload.get("message", f"{e.event_type} recorded")
                }
                for e in timeline
            ],
            "system_statistics": self.read_model.metrics_service.get_current_metrics()
        }

    def get_alert_centre_view(self) -> Dict[str, Any]:
        """Expose categorised notification lists, history records, and queue status."""
        notifications_history = self.read_model.notification_service.history.load()
        notifications_queue = self.read_model.notification_service.queue.load()
        
        unread = [n for n in notifications_queue if n.payload.get("delivery_status") == "PENDING"]
        critical = [n for n in notifications_history if n.severity == "CRITICAL"]
        warning = [n for n in notifications_history if n.severity == "WARNING"]
        informational = [n for n in notifications_history if n.severity == "INFO"]
        
        return {
            "unread_alerts": [
                {
                    "alert_id": n.event_id,
                    "title": n.payload.get("title", "No Title"),
                    "message": n.payload.get("message", ""),
                    "timestamp": n.timestamp
                }
                for n in unread
            ],
            "critical_alerts": [
                {
                    "alert_id": n.event_id,
                    "title": n.payload.get("title", "Critical Alert"),
                    "message": n.payload.get("message", ""),
                    "timestamp": n.timestamp
                }
                for n in critical
            ],
            "warning_alerts": [
                {
                    "alert_id": n.event_id,
                    "title": n.payload.get("title", "Warning Alert"),
                    "message": n.payload.get("message", ""),
                    "timestamp": n.timestamp
                }
                for n in warning
            ],
            "informational_alerts": [
                {
                    "alert_id": n.event_id,
                    "title": n.payload.get("title", "Info Alert"),
                    "message": n.payload.get("message", ""),
                    "timestamp": n.timestamp
                }
                for n in informational
            ],
            "notification_history": [
                {
                    "timestamp": n.timestamp,
                    "status": n.payload.get("delivery_status", "UNKNOWN"),
                    "channels": n.payload.get("delivery_channels", [])
                }
                for n in notifications_history
            ],
            "queue_status": {
                "depth": len(notifications_queue),
                "is_empty": len(notifications_queue) == 0
            }
        }

    def get_reporting_portal_view(self) -> Dict[str, Any]:
        """Expose report archive browser logs, metadata, and scheduled items."""
        history = self.read_model.reporting_service.history.load()
        scheduled_jobs = self.read_model.reporting_service.scheduler.get_due_jobs(time.time() + 86400)
        
        return {
            "available_reports": [
                {"type": "DAILY_OPERATIONAL_SUMMARY", "name": "Daily Operational Summary"},
                {"type": "WEEKLY_COMPLIANCE_AUDIT", "name": "Weekly Compliance Audit"}
            ],
            "recent_reports": [
                {
                    "report_id": r.event_id,
                    "title": r.payload.get("title", "Report"),
                    "timestamp": r.timestamp
                }
                for r in history[-10:]
            ],
            "scheduled_reports": [
                {
                    "job_id": j.job_id,
                    "title": j.title,
                    "report_type": j.report_type,
                    "interval_seconds": j.interval_seconds
                }
                for j in scheduled_jobs
            ],
            "report_history": [
                {
                    "report_id": r.event_id,
                    "title": r.payload.get("title", "Report"),
                    "timestamp": r.timestamp,
                    "metadata": r.payload.get("custom_payload", {})
                }
                for r in history
            ]
        }
