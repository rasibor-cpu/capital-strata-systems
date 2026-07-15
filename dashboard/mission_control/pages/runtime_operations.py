from __future__ import annotations

from dashboard.mission_control.pages._components import detail_table, metric_grid, page_header, section, split_panels


def render(state: dict) -> str:
    runtime = section(state, "runtime")
    subsystem = runtime.get("subsystem_health", {}) if isinstance(runtime.get("subsystem_health"), dict) else {}
    return (
        page_header("Runtime Operations", "Read-only runtime cycle, supervisor, dependency, API, dashboard, mobile, and certification visibility.")
        + metric_grid(
            (
                ("Runtime Status", runtime.get("runtime_status"), runtime.get("runtime_status")),
                ("Runtime Mode", runtime.get("runtime_mode"), runtime.get("runtime_mode")),
                ("Engine Mode", runtime.get("engine_mode"), "neutral"),
                ("Cycle", runtime.get("cycle"), "neutral"),
                ("Heartbeat", runtime.get("heartbeat"), runtime.get("heartbeat_status")),
                ("Source", runtime.get("source"), runtime.get("source")),
                ("Certification", subsystem.get("certification"), subsystem.get("certification")),
            )
        )
        + split_panels(
            detail_table("Runtime Counters", {
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
            }),
            detail_table("Subsystem Health", subsystem),
            detail_table("Disabled Controls", runtime.get("controls", {})),
        )
    )
