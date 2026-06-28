"""
Health Metrics Evaluator for CSS Observability Subsystem

Computes normalized derived health scores for CSS enterprise subsystems.
"""

from typing import Dict, Any

class HealthEvaluator:
    """
    Derived health score calculator.
    
    Responsibility: Convert counter states to 0-100 normalized indexes.
    """
    @staticmethod
    def calculate_health(
        restart_count: int,
        heartbeat_age: float,
        notif_delivered: int,
        notif_failed: int,
        report_backlog: int,
        subscriber_failures: int
    ) -> Dict[str, Any]:
        """Derive subsystem health scores and overall average enterprise score."""
        # 1. Runtime Health
        runtime_score = 100.0 - (restart_count * 15.0)
        if heartbeat_age > 300.0:
            runtime_score -= 50.0
        runtime_score = max(0.0, min(100.0, runtime_score))

        # 2. Notification Health
        total_notifs = notif_delivered + notif_failed
        notif_score = 100.0
        if total_notifs > 0:
            fail_rate = notif_failed / total_notifs
            notif_score -= (fail_rate * 100.0)
        notif_score = max(0.0, min(100.0, notif_score))

        # 3. Reporting Health
        reporting_score = 100.0 - (report_backlog * 5.0)
        reporting_score = max(0.0, min(100.0, reporting_score))

        # 4. Operations Health
        ops_score = 100.0 - (subscriber_failures * 10.0)
        ops_score = max(0.0, min(100.0, ops_score))

        # Derived Overall Health
        overall_score = (runtime_score + notif_score + reporting_score + ops_score) / 4.0

        return {
            "runtime_health": runtime_score,
            "notification_health": notif_score,
            "reporting_health": reporting_score,
            "operations_health": ops_score,
            "overall_health_score": overall_score
        }
