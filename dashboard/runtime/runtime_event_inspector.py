from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from dashboard.runtime.runtime_event_bus import (
    RuntimeEventBus,
    safe_json_dumps,
)


RUNTIME_EVENT_INSPECTOR_VERSION = "css.runtime_event_inspector.v1"
DEFAULT_RUNTIME_EVENT_LIMIT = 100
MAX_RUNTIME_EVENT_SCAN_LIMIT = 5000


def get_runtime_event_inspection_payload(
    event_bus: RuntimeEventBus | None = None,
    *,
    event_type: str = "",
    subsystem: str = "",
    severity: str = "",
    correlation_id: str = "",
    limit: int = DEFAULT_RUNTIME_EVENT_LIMIT,
) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    filters = {
        "event_type": str(event_type or ""),
        "subsystem": str(subsystem or ""),
        "severity": str(severity or ""),
        "correlation_id": str(correlation_id or ""),
        "limit": safe_limit,
    }

    if event_bus is None:
        events: tuple[dict[str, Any], ...] = ()
    else:
        events = event_bus.get_recent(
            MAX_RUNTIME_EVENT_SCAN_LIMIT,
            subsystem=subsystem,
            event_type=event_type,
            severity=severity,
        )

    filtered = _filter_by_correlation(events, correlation_id)
    limited = tuple(filtered[-safe_limit:]) if safe_limit else ()
    safe_events = [_json_safe_event(event) for event in limited]

    return {
        "payload_version": RUNTIME_EVENT_INSPECTOR_VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "source": "runtime_event_bus",
        "bus_available": event_bus is not None,
        "filters": filters,
        "total_returned": len(safe_events),
        "empty": len(safe_events) == 0,
        "summary": summarize_runtime_events(safe_events),
        "events": safe_events,
    }


def summarize_runtime_events(events: list[Mapping[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "total_events": len(events),
        "counts_by_subsystem": {},
        "counts_by_event_type": {},
        "counts_by_severity": {},
    }

    for event in events:
        subsystem = str(event.get("subsystem") or "UNKNOWN")
        event_type = str(event.get("event_type") or "UNKNOWN")
        severity = str(event.get("severity") or "UNKNOWN").upper()
        summary["counts_by_subsystem"][subsystem] = (
            summary["counts_by_subsystem"].get(subsystem, 0) + 1
        )
        summary["counts_by_event_type"][event_type] = (
            summary["counts_by_event_type"].get(event_type, 0) + 1
        )
        summary["counts_by_severity"][severity] = (
            summary["counts_by_severity"].get(severity, 0) + 1
        )

    return summary


def _filter_by_correlation(
    events: tuple[dict[str, Any], ...],
    correlation_id: str,
) -> tuple[dict[str, Any], ...]:
    correlation_filter = str(correlation_id or "").strip().upper()
    if not correlation_filter:
        return events
    return tuple(
        event
        for event in events
        if str(event.get("correlation_id") or "").strip().upper() == correlation_filter
    )


def _json_safe_event(event: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(safe_json_dumps(dict(event)))


def _safe_limit(value: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = DEFAULT_RUNTIME_EVENT_LIMIT
    return max(0, min(parsed, MAX_RUNTIME_EVENT_SCAN_LIMIT))


__all__ = [
    "DEFAULT_RUNTIME_EVENT_LIMIT",
    "MAX_RUNTIME_EVENT_SCAN_LIMIT",
    "RUNTIME_EVENT_INSPECTOR_VERSION",
    "get_runtime_event_inspection_payload",
    "summarize_runtime_events",
]
