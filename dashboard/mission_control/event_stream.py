from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dashboard.runtime.frontend_contract import DATA_UNAVAILABLE


ALERT_CATEGORIES = ("runtime", "broker", "risk", "market", "portfolio", "execution", "certification")
SEVERITIES = ("INFO", "WARNING", "ERROR", "CRITICAL")


def build_event_stream(state: Mapping[str, Any]) -> dict[str, Any]:
    timeline = _mapping(state.get("operations_timeline"))
    alerts = _mapping(state.get("alerts"))
    events = list(timeline.get("events", [])) if isinstance(timeline.get("events"), list) else []
    return {
        "status": "AVAILABLE" if events else "UNAVAILABLE",
        "events": events,
        "event_count": len(events),
        "alert_count": alerts.get("count", DATA_UNAVAILABLE),
        "queue_depth": DATA_UNAVAILABLE,
        "read_only": True,
        **_metadata(state, "event_stream"),
    }


def build_alert_center(state: Mapping[str, Any]) -> dict[str, Any]:
    alerts = _mapping(state.get("alerts"))
    active_alerts = list(alerts.get("active_alerts", [])) if isinstance(alerts.get("active_alerts"), list) else []
    grouped_by_severity = {severity: [] for severity in SEVERITIES}
    grouped_by_category = {category: [] for category in ALERT_CATEGORIES}
    for alert in active_alerts:
        if not isinstance(alert, Mapping):
            continue
        severity = str(alert.get("severity", "INFO")).upper()
        category = str(alert.get("category", "runtime")).lower()
        grouped_by_severity.setdefault(severity, []).append(dict(alert))
        grouped_by_category.setdefault(category, []).append(dict(alert))
    return {
        "status": alerts.get("severity", DATA_UNAVAILABLE),
        "active_alerts": active_alerts,
        "incident_timeline": alerts.get("incident_timeline", []),
        "grouped_by_severity": grouped_by_severity,
        "grouped_by_category": grouped_by_category,
        "acknowledgement_actions": "DISABLED_READ_ONLY",
        "external_notifications": alerts.get("external_notifications", "DISABLED"),
        "read_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
        **_metadata(state, "alert_center"),
    }


def _metadata(state: Mapping[str, Any], source_module: str) -> dict[str, Any]:
    runtime = _mapping(state.get("runtime"))
    snapshot = _mapping(state.get("runtime_snapshot"))
    freshness = _mapping(state.get("freshness"))
    return {
        "source": runtime.get("source", snapshot.get("source", DATA_UNAVAILABLE)),
        "source_module": f"dashboard.mission_control.{source_module}",
        "provenance": snapshot.get("provenance", {}),
        "generated_at": state.get("generated_at", DATA_UNAVAILABLE),
        "freshness": freshness.get("overall_freshness", DATA_UNAVAILABLE),
        "state_hash": runtime.get("state_hash", snapshot.get("state_hash", DATA_UNAVAILABLE)),
    }


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


__all__ = ["build_alert_center", "build_event_stream"]
