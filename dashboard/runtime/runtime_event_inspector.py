from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from dashboard.runtime.runtime_event_bus import (
    RuntimeEventBus,
    safe_json_dumps,
)


RUNTIME_EVENT_INSPECTOR_VERSION = "css.runtime_event_inspector.v1"
RUNTIME_EVENT_RETENTION_POLICY_VERSION = "css.runtime_event_retention_policy.v1"
DEFAULT_RUNTIME_EVENT_LIMIT = 100
MAX_RUNTIME_EVENT_SCAN_LIMIT = 5000
MAX_RUNTIME_EVENT_EXPORT_LIMIT = 1000


@dataclass(frozen=True)
class RuntimeEventRetentionPolicy:
    max_events: int = MAX_RUNTIME_EVENT_SCAN_LIMIT
    max_export_limit: int = MAX_RUNTIME_EVENT_EXPORT_LIMIT
    default_inspection_limit: int = DEFAULT_RUNTIME_EVENT_LIMIT
    redaction_required: bool = True
    allow_export: bool = True
    export_format: str = "json"
    policy_version: str = RUNTIME_EVENT_RETENTION_POLICY_VERSION

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


DEFAULT_RUNTIME_EVENT_RETENTION_POLICY = RuntimeEventRetentionPolicy()


def get_runtime_event_inspection_payload(
    event_bus: RuntimeEventBus | None = None,
    *,
    event_type: str = "",
    subsystem: str = "",
    severity: str = "",
    correlation_id: str = "",
    limit: int | None = None,
    export: bool = False,
    policy: RuntimeEventRetentionPolicy = DEFAULT_RUNTIME_EVENT_RETENTION_POLICY,
) -> dict[str, Any]:
    safe_limit = _safe_limit(limit, policy=policy, export=export)
    filters = {
        "event_type": str(event_type or ""),
        "subsystem": str(subsystem or ""),
        "severity": str(severity or ""),
        "correlation_id": str(correlation_id or ""),
        "limit": safe_limit,
        "export": bool(export),
    }

    if event_bus is None:
        events: tuple[dict[str, Any], ...] = ()
    else:
        events = event_bus.get_recent(
            max(0, int(policy.max_events or 0)),
            subsystem=subsystem,
            event_type=event_type,
            severity=severity,
        )

    filtered = _filter_by_correlation(events, correlation_id)
    limited = tuple(filtered[-safe_limit:]) if safe_limit else ()
    safe_events = [_json_safe_event(event) for event in limited]

    payload = {
        "payload_version": RUNTIME_EVENT_INSPECTOR_VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "source": "runtime_event_bus",
        "bus_available": event_bus is not None,
        "retention_policy": policy.as_dict(),
        "redaction_applied": bool(policy.redaction_required),
        "export_requested": bool(export),
        "filters": filters,
        "total_returned": len(safe_events),
        "empty": len(safe_events) == 0,
        "summary": summarize_runtime_events(safe_events),
        "events": safe_events,
    }
    if export:
        payload["export"] = build_runtime_event_export_payload(
            safe_events,
            policy=policy,
        )
    return payload


def export_runtime_events(
    event_bus: RuntimeEventBus | None = None,
    *,
    event_type: str = "",
    subsystem: str = "",
    severity: str = "",
    correlation_id: str = "",
    limit: int | None = None,
    policy: RuntimeEventRetentionPolicy = DEFAULT_RUNTIME_EVENT_RETENTION_POLICY,
) -> dict[str, Any]:
    return get_runtime_event_inspection_payload(
        event_bus,
        event_type=event_type,
        subsystem=subsystem,
        severity=severity,
        correlation_id=correlation_id,
        limit=limit,
        export=True,
        policy=policy,
    )


def build_runtime_event_export_payload(
    events: list[Mapping[str, Any]],
    *,
    policy: RuntimeEventRetentionPolicy = DEFAULT_RUNTIME_EVENT_RETENTION_POLICY,
) -> dict[str, Any]:
    if not policy.allow_export:
        return {
            "allowed": False,
            "format": policy.export_format,
            "event_count": 0,
            "redaction_required": bool(policy.redaction_required),
            "events": [],
        }

    return {
        "allowed": True,
        "format": policy.export_format,
        "event_count": len(events),
        "redaction_required": bool(policy.redaction_required),
        "events": [_json_safe_event(event) for event in events],
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


def _safe_limit(
    value: int | None,
    *,
    policy: RuntimeEventRetentionPolicy,
    export: bool,
) -> int:
    try:
        parsed = int(value) if value is not None else int(policy.default_inspection_limit)
    except Exception:
        parsed = int(policy.default_inspection_limit)
    max_allowed = policy.max_export_limit if export else policy.max_events
    return max(0, min(parsed, max(0, int(max_allowed or 0))))


__all__ = [
    "DEFAULT_RUNTIME_EVENT_LIMIT",
    "DEFAULT_RUNTIME_EVENT_RETENTION_POLICY",
    "MAX_RUNTIME_EVENT_EXPORT_LIMIT",
    "MAX_RUNTIME_EVENT_SCAN_LIMIT",
    "RUNTIME_EVENT_INSPECTOR_VERSION",
    "RUNTIME_EVENT_RETENTION_POLICY_VERSION",
    "RuntimeEventRetentionPolicy",
    "build_runtime_event_export_payload",
    "export_runtime_events",
    "get_runtime_event_inspection_payload",
    "summarize_runtime_events",
]
