"""
Executive Summary Builder for CSS Operations Platform
"""

from typing import Dict, Any
from backend.dashboard.dashboard_read_model import DashboardReadModel

class ExecutiveSummaryBuilder:
    """
    Assembles operations stats into high-level dashboard payloads.
    """
    def __init__(self, read_model: DashboardReadModel):
        self.read_model = read_model

    def build_summary(self) -> Dict[str, Any]:
        """Aggregate health, status, engine, and metrics summary."""
        health = self.read_model.get_enterprise_health()
        metrics = self.read_model.metrics_service.get_current_metrics()
        
        return {
            "enterprise_health_score": health.get("overall_health_score", 100.0),
            "runtime_status": self.read_model.get_runtime_status(),
            "engine_mode": self.read_model.get_engine_mode(),
            "recent_events_count": metrics.get("events_published", 0),
            "active_alerts_count": len(self.read_model.get_active_alerts()),
            "outstanding_notifications_count": len(self.read_model.get_outstanding_notifications()),
            "metrics_summary": metrics,
            "subsystem_health": health
        }
