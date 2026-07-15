from __future__ import annotations

from dashboard.mission_control.pages._components import detail_table, metric_grid, page_header, section, split_panels


def render(state: dict) -> str:
    alerts = section(state, "alerts")
    return (
        page_header("Alerts and Incidents", "Read-only active alerts, severity, source, evidence, acknowledgments, runtime failures, and incident timeline.")
        + metric_grid(
            (
                ("Active Alerts", alerts.get("count"), "good" if alerts.get("count") == 0 else "warn"),
                ("Severity", alerts.get("severity"), alerts.get("severity")),
                ("Heartbeat", alerts.get("heartbeat_status"), alerts.get("heartbeat_status")),
                ("External Notifications", alerts.get("external_notifications"), alerts.get("external_notifications")),
            )
        )
        + split_panels(
            detail_table("Active Alerts", alerts.get("active_alerts", [])),
            detail_table("Incident Timeline", alerts.get("incident_timeline", [])),
        )
    )
