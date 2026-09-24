from __future__ import annotations

from dashboard.mission_control.pages._components import detail_table, metric_grid, page_header, section


def _anchor_panel(anchor: str, content: str) -> str:
    return f'<div class="mc-section-anchor" id="{anchor}">{content}</div>'


def render(state: dict) -> str:
    alerts = section(state, "alerts")
    center = section(state, "alert_center")
    return (
        page_header("Alerts and Incidents", "Read-only active alerts, severity, source, evidence, acknowledgments, runtime failures, and incident timeline.")
        + '<nav class="mc-page-jump" aria-label="Alerts and incidents sections">'
          '<a href="#mc-active-alerts">Active Alerts</a>'
          '<a href="#mc-alert-center">Alert Center</a>'
          '<a href="#mc-incident-timeline">Timeline</a>'
          '</nav>'
        + metric_grid(
            (
                ("Active Alerts", alerts.get("count"), "good" if alerts.get("count") == 0 else "warn"),
                ("Severity", alerts.get("severity"), alerts.get("severity")),
                ("Heartbeat", alerts.get("heartbeat_status"), alerts.get("heartbeat_status")),
                ("External Notifications", alerts.get("external_notifications"), alerts.get("external_notifications")),
            ),
            css_class="mc-metric-grid mc-alert-priority",
            aria_label="Alert triage priority",
        )
        + '<div class="mc-alert-stack">'
        + _anchor_panel("mc-active-alerts", detail_table("Active Alerts", alerts.get("active_alerts", [])))
        + _anchor_panel(
            "mc-alert-center",
            detail_table(
                "Alert Center",
                {
                    "grouped_by_severity": center.get("grouped_by_severity"),
                    "grouped_by_category": center.get("grouped_by_category"),
                    "acknowledgement_actions": center.get("acknowledgement_actions"),
                    "source": center.get("source"),
                    "state_hash": center.get("state_hash"),
                },
            ),
        )
        + _anchor_panel("mc-incident-timeline", detail_table("Incident Timeline", alerts.get("incident_timeline", [])))
        + '</div>'
    )
