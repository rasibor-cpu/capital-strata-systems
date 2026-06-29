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
    def __init__(
        self,
        read_model: DashboardReadModel,
        intelligence_service: Any = None,
        certification_engine: Any = None,
        optimization_service: Any = None
    ):
        self.read_model = read_model
        self.intelligence_service = intelligence_service
        self.certification_engine = certification_engine
        self.optimization_service = optimization_service
        self.summary_builder = ExecutiveSummaryBuilder(read_model)

    def get_executive_summary(self) -> Dict[str, Any]:
        """Aggregate high-level summary overview indicators."""
        return self.summary_builder.build_summary()

    def get_executive_readiness_view(self) -> Dict[str, Any]:
        """Expose read-only production certification status for the executive dashboard."""
        return self.get_certification_readiness_view()

    def get_certification_readiness_view(self) -> Dict[str, Any]:
        """Expose the certification dashboard section without recalculating readiness."""
        if not self.certification_engine:
            return {
                "overall_readiness_score": 0.0,
                "certification_status": "WARNING",
                "critical_findings_count": 0,
                "warning_count": 1,
                "information_count": 0,
                "last_certification_time": None,
            }

        if hasattr(self.certification_engine, "get_dashboard_section"):
            return self.certification_engine.get_dashboard_section()

        checks = self.certification_engine.run_production_checks()
        return {
            "overall_readiness_score": checks.get("overall_readiness_score", 0.0),
            "certification_status": checks.get("certification_status", checks.get("deployment_recommendation", "WARNING")),
            "critical_findings_count": len(checks.get("critical_findings", [])),
            "warning_count": len(checks.get("warnings", [])),
            "information_count": len(checks.get("informational_findings", checks.get("info_findings", []))),
            "last_certification_time": checks.get("generated_at"),
        }

    def get_optimization_advisory_view(self) -> Dict[str, Any]:
        """Expose advisory optimization recommendations for dashboard review."""
        if not self.optimization_service:
            return {
                "advisory_only": True,
                "execution_allowed": False,
                "overall_recommendations": [],
                "parameter_tuning": {},
                "allocation_tuning": {},
                "confidence_threshold": None,
                "risk_tuning": {},
                "gap_recommendations": [],
            }

        optimizations = self.optimization_service.get_optimizations()
        return {
            "advisory_only": True,
            "execution_allowed": False,
            "overall_recommendations": optimizations.get("overall_recommendations", []),
            "parameter_tuning": optimizations.get("parameter_tuning", {}),
            "allocation_tuning": optimizations.get("allocation_tuning", {}),
            "confidence_threshold": optimizations.get("confidence_threshold"),
            "risk_tuning": optimizations.get("risk_tuning", {}),
            "gap_recommendations": optimizations.get("gap_recommendations", []),
        }

    def get_trading_intelligence_view(self) -> Dict[str, Any]:
        """Expose Trading Intelligence metrics and communications health indicators."""
        if not self.intelligence_service:
            return {
                "market_regime": "UNKNOWN",
                "trading_confidence": 0.0,
                "strategy_performance": {},
                "portfolio_health": {},
                "top_recommendations": [],
                "delivery_status": {},
                "communication_health": 100.0
            }
            
        report = self.intelligence_service.get_trading_intelligence_report()
        health = self.read_model.get_enterprise_health()
        
        # Get delivery status counts
        notif_history = self.read_model.notification_service.history.load()
        queued = self.read_model.notification_service.queue.load()
        
        delivery_status = {
            "queued": len(queued),
            "delivered": len([n for n in notif_history if n.payload.get("delivery_status") == "SENT"]),
            "failed": len([n for n in notif_history if n.payload.get("delivery_status") == "FAILED"])
        }
        
        return {
            "market_regime": report["market_regime"],
            "trading_confidence": report["advisory_confidence_score"],
            "strategy_performance": {
                "win_loss": report["win_loss_statistics"],
                "drawdowns": report["drawdown_trends"],
                "asset_performance": report["asset_class_performance"]
            },
            "portfolio_health": report["portfolio_concentration"],
            "top_recommendations": report["recommendations"],
            "delivery_status": delivery_status,
            "communication_health": health.get("notification_health", 100.0)
        }

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
