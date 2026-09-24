from __future__ import annotations

from dashboard.mission_control.pages._components import detail_table, metric_grid, page_header, section


def _anchor_panel(anchor: str, content: str) -> str:
    return f'<div class="mc-section-anchor" id="{anchor}">{content}</div>'


def _evidence_panel(anchor: str, title: str, content: str) -> str:
    return (
        f'<div class="mc-section-anchor mc-evidence-disclosure" id="{anchor}">'
        f'<details><summary>{title}</summary>{content}</details>'
        '</div>'
    )


def _runtime_snapshot(runtime: dict) -> dict:
    return {
        "uptime": runtime.get("uptime"),
        "restart_count": runtime.get("restart_count"),
        "failure_count": runtime.get("failure_count"),
        "recovery_count": runtime.get("recovery_count"),
        "alert_count": runtime.get("alert_count"),
        "disconnect_count": runtime.get("disconnect_count"),
        "last_successful_cycle": runtime.get("last_successful_cycle", "UNAVAILABLE"),
        "last_failed_cycle": runtime.get("last_failed_cycle", "UNAVAILABLE"),
        "heartbeat_status": runtime.get("heartbeat_status"),
        "heartbeat_age_seconds": runtime.get("heartbeat_age_seconds"),
    }


def render(state: dict) -> str:
    runtime = section(state, "runtime")
    timeline = section(state, "operations_timeline")
    event_stream = section(state, "event_stream")
    metrics = section(state, "system_metrics")
    consistency = section(state, "source_consistency")
    subsystem = runtime.get("subsystem_health", {}) if isinstance(runtime.get("subsystem_health"), dict) else {}
    return (
        page_header("Runtime Operations", "Read-only runtime cycle, supervisor, dependency, API, dashboard, mobile, and certification visibility.")
        + '<nav class="mc-page-jump" aria-label="Runtime Operations sections">'
          '<a href="#mc-runtime-health">Health</a>'
          '<a href="#mc-runtime-metrics">Metrics</a>'
          '<a href="#mc-runtime-timeline">Timeline</a>'
          '<a href="#mc-runtime-evidence">Evidence</a>'
          '</nav>'
        + metric_grid(
            (
                ("Runtime Status", runtime.get("runtime_status"), runtime.get("runtime_status")),
                ("Heartbeat", runtime.get("heartbeat"), runtime.get("heartbeat_status")),
                ("Certification", subsystem.get("certification"), subsystem.get("certification")),
                ("Runtime Mode", runtime.get("runtime_mode"), runtime.get("runtime_mode")),
            ),
            css_class="mc-metric-grid mc-metric-grid-priority mc-runtime-priority",
            aria_label="Runtime Operations priority",
        )
        + metric_grid(
            (
                ("Engine Mode", runtime.get("engine_mode"), "neutral"),
                ("Cycle", runtime.get("cycle"), "neutral"),
                ("Source", runtime.get("source"), runtime.get("source")),
            ),
            css_class="mc-metric-grid mc-metric-grid-secondary",
            aria_label="Runtime Operations secondary metrics",
        )
        + '<div class="mc-operator-stack">'
        + _anchor_panel("mc-runtime-health", detail_table("Runtime Snapshot", _runtime_snapshot(runtime)))
        + _anchor_panel("mc-runtime-metrics", detail_table("System Metrics", {
            "cpu": metrics.get("cpu"),
            "memory": metrics.get("memory"),
            "runtime_latency": metrics.get("runtime_latency"),
            "api_latency": metrics.get("api_latency"),
            "refresh_interval_seconds": metrics.get("refresh_interval_seconds"),
            "event_queue": metrics.get("event_queue"),
            "cycle_duration": metrics.get("cycle_duration"),
            "runtime_age": metrics.get("runtime_age"),
            "heartbeat_age": metrics.get("heartbeat_age"),
        }))
        + _anchor_panel("mc-runtime-subsystems", detail_table("Subsystem Health", subsystem))
        + _anchor_panel("mc-runtime-events", detail_table("Event Stream", {
            "event_count": event_stream.get("event_count"),
            "alert_count": event_stream.get("alert_count"),
            "queue_depth": event_stream.get("queue_depth"),
            "source": event_stream.get("source"),
        }))
        + _evidence_panel("mc-runtime-timeline", "Show operations timeline", detail_table("Operations Timeline", timeline.get("events", [])))
        + _evidence_panel("mc-runtime-evidence", "Show source-consistency evidence", detail_table("Source Consistency", consistency))
        + _evidence_panel("mc-runtime-counter-evidence", "Show full runtime counter evidence", detail_table("Runtime Counter Evidence (Full)", {
            "uptime": runtime.get("uptime"),
            "restart_count": runtime.get("restart_count"),
            "failure_count": runtime.get("failure_count"),
            "recovery_count": runtime.get("recovery_count"),
            "alert_count": runtime.get("alert_count"),
            "disconnect_count": runtime.get("disconnect_count"),
            "last_successful_cycle": runtime.get("last_successful_cycle", "UNAVAILABLE"),
            "last_failed_cycle": runtime.get("last_failed_cycle", "UNAVAILABLE"),
            "heartbeat_status": runtime.get("heartbeat_status"),
            "heartbeat_age_seconds": runtime.get("heartbeat_age_seconds"),
            "state_hash": runtime.get("state_hash"),
        }))
        + _evidence_panel("mc-runtime-controls", "Show disabled controls", detail_table("Disabled Controls", runtime.get("controls", {})))
        + '</div>'
    )
