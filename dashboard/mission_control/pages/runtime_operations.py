from __future__ import annotations

from dashboard.mission_control.pages._components import detail_table, metric_grid, page_header, section, warning_banner


def _anchor_panel(anchor: str, content: str) -> str:
    return f'<div class="mc-section-anchor" id="{anchor}">{content}</div>'


def _evidence_panel(anchor: str, title: str, content: str) -> str:
    return (
        f'<div class="mc-section-anchor mc-evidence-disclosure" id="{anchor}">'
        f'<details><summary>{title}</summary>{content}</details>'
        '</div>'
    )


def _metric_status(value: object) -> object:
    return "UNAVAILABLE" if value in (None, "") else value


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
    freshness_token = str(runtime.get("source_freshness") or runtime.get("heartbeat_status") or "UNAVAILABLE").strip().upper()
    source_status = str(runtime.get("source_status") or "UNAVAILABLE").strip().upper()
    stale_or_unavailable = freshness_token in {"STALE", "EXPIRED", "UNAVAILABLE", "UNKNOWN"} or source_status == "RED"
    source_summary = {
        "selected_source": runtime.get("selected_source", "UNAVAILABLE"),
        "authoritative_source": runtime.get("authoritative_source", runtime.get("source", "UNAVAILABLE")),
        "fallback_source": runtime.get("fallback_source", "UNAVAILABLE"),
        "available_sources": runtime.get("available_sources", []),
        "source_freshness": runtime.get("source_freshness", "UNAVAILABLE"),
        "source_confidence": runtime.get("source_confidence", "UNAVAILABLE"),
        "source_status": runtime.get("source_status", "UNAVAILABLE"),
        "source_disagreement": runtime.get("source_disagreement", False),
        "supervisor_state": runtime.get("supervisor_state", "UNAVAILABLE"),
        "heartbeat_status": runtime.get("heartbeat_status", "UNAVAILABLE"),
        "heartbeat_age_seconds": runtime.get("heartbeat_age_seconds", "UNAVAILABLE"),
    }
    return (
        page_header("Runtime Operations", "Read-only runtime cycle, supervisor, dependency, API, dashboard, mobile, and certification visibility.")
        + (
            warning_banner(
                "AUTHORITATIVE RUNTIME EVIDENCE IS STALE OR UNAVAILABLE — runtime conclusions remain fail-closed until the canonical supervisor/source refreshes.",
                status="warn",
            )
            if stale_or_unavailable
            else warning_banner(
                "Authoritative runtime evidence is current enough for read-only operational visibility.",
                status="good",
            )
        )
        + '<nav class="mc-page-jump" aria-label="Runtime Operations sections">'
          '<a href="#mc-runtime-health">Health</a>'
          '<a href="#mc-runtime-metrics">Metrics</a>'
          '<a href="#mc-runtime-timeline">Timeline</a>'
          '<a href="#mc-runtime-evidence">Evidence</a>'
          '</nav>'
        + metric_grid(
            (
                ("Runtime Status", runtime.get("runtime_status"), _metric_status(runtime.get("runtime_status"))),
                ("Heartbeat Status", runtime.get("heartbeat_status"), _metric_status(runtime.get("heartbeat_status"))),
                ("Certification", subsystem.get("certification"), _metric_status(subsystem.get("certification"))),
                ("Runtime Mode", runtime.get("runtime_mode"), _metric_status(runtime.get("runtime_mode"))),
            ),
            css_class="mc-metric-grid mc-metric-grid-priority mc-runtime-priority",
            aria_label="Runtime Operations priority",
        )
        + metric_grid(
            (
                ("Engine Mode", runtime.get("engine_mode"), _metric_status(runtime.get("engine_mode"))),
                ("Cycle", runtime.get("cycle"), "neutral"),
                ("Heartbeat At", runtime.get("heartbeat"), "warn" if stale_or_unavailable else "neutral"),
                ("Source", runtime.get("authoritative_source", runtime.get("source")), "warn" if stale_or_unavailable else "neutral"),
            ),
            css_class="mc-metric-grid mc-metric-grid-secondary",
            aria_label="Runtime Operations secondary metrics",
        )
        + '<div class="mc-operator-stack">'
        + _anchor_panel("mc-runtime-health", detail_table("Runtime Snapshot", _runtime_snapshot(runtime)))
        + _anchor_panel("mc-runtime-source", detail_table("Runtime Source & Freshness", source_summary))
        + _anchor_panel("mc-runtime-metrics", detail_table("System Metrics", {
            "source_system": metrics.get("source_selected"),
            "active_broker": metrics.get("active_broker"),
            "broker_mode": metrics.get("broker_mode"),
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
        + '<section class="mc-panel mc-section-anchor" id="mc-client-system-metrics">'
          '<h2>Current Device / Browser Metrics</h2>'
          '<p class="mc-muted">Automatically detected from the device and browser currently operating CSS. Availability depends on browser support.</p>'
          '<div class="mc-table-wrap"><table><tbody id="mc-client-metrics-body">'
          '<tr><th>device</th><td>Detecting…</td></tr></tbody></table></div></section>'
        + """<script>
(function () {
  const body = document.getElementById('mc-client-metrics-body');
  if (!body) return;
  const nav = window.navigator || {};
  const connection = nav.connection || nav.mozConnection || nav.webkitConnection || {};
  const rows = {
    platform: nav.userAgentData?.platform || nav.platform || 'UNAVAILABLE',
    browser_user_agent: nav.userAgent || 'UNAVAILABLE',
    logical_processors: nav.hardwareConcurrency || 'UNAVAILABLE',
    device_memory_gb: nav.deviceMemory || 'UNAVAILABLE',
    online: typeof nav.onLine === 'boolean' ? nav.onLine : 'UNAVAILABLE',
    network_type: connection.effectiveType || 'UNAVAILABLE',
    downlink_mbps: connection.downlink || 'UNAVAILABLE',
    viewport: window.innerWidth + ' × ' + window.innerHeight,
    screen: window.screen ? (window.screen.width + ' × ' + window.screen.height) : 'UNAVAILABLE',
    pixel_ratio: window.devicePixelRatio || 1
  };
  body.innerHTML = Object.entries(rows).map(([k,v]) =>
    '<tr><th>' + String(k).replaceAll('_',' ') + '</th><td>' + String(v) + '</td></tr>'
  ).join('');
})();
</script>"""
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
