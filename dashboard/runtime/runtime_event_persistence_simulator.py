from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from dashboard.runtime.runtime_event_bus import (
    RUNTIME_EVENT_REDACTION_STATUS,
    RuntimeEventBus,
    normalize_runtime_event,
    safe_json_dumps,
)
from dashboard.runtime.runtime_event_inspector import (
    DEFAULT_RUNTIME_EVENT_RETENTION_POLICY,
    RuntimeEventRetentionPolicy,
)
from dashboard.runtime.runtime_event_persistence_policy import (
    DEFAULT_RUNTIME_EVENT_PERSISTENCE_POLICY,
    RuntimeEventPersistencePolicy,
    validate_persistence_request,
)


RUNTIME_EVENT_PERSISTENCE_SIMULATOR_VERSION = (
    "css.runtime_event_persistence_simulator.v1"
)
_SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "secret",
    "token",
    "password",
    "credential",
    "private",
    "pem",
    "authorization",
    "bearer",
)


@dataclass(frozen=True)
class RuntimeEventPersistenceSimulationResult:
    simulation_id: str
    accepted_events_count: int
    rejected_events_count: int
    rejection_reasons: dict[str, int]
    redaction_failures: list[dict[str, Any]]
    estimated_storage_bytes: int
    estimated_event_rate: float
    subsystem_breakdown: dict[str, dict[str, int]]
    simulated_timestamp: str
    inspected_events_count: int
    truncated_events_count: int
    evaluated_events_count: int
    event_results: list[dict[str, Any]]
    persistence_enabled: bool = False
    writes_performed: bool = False
    simulation_only: bool = True
    read_only: bool = True
    payload_version: str = RUNTIME_EVENT_PERSISTENCE_SIMULATOR_VERSION
    retention_policy: dict[str, Any] = field(default_factory=dict)
    persistence_policy: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def simulate_runtime_event_persistence(
    events: Iterable[Mapping[str, Any]] | None = None,
    *,
    retention_policy: RuntimeEventRetentionPolicy = DEFAULT_RUNTIME_EVENT_RETENTION_POLICY,
    persistence_policy: RuntimeEventPersistencePolicy = DEFAULT_RUNTIME_EVENT_PERSISTENCE_POLICY,
    limit: int | None = None,
    requested_window_minutes: int = 15,
    reason: str = "runtime event persistence dry-run simulation",
    operator_id: str = "",
    approval_token_present: bool = False,
    requested_export_format: str = "json",
    timestamp_utc: str = "",
) -> dict[str, Any]:
    raw_events = list(events or [])
    safe_limit = _safe_limit(limit, retention_policy)
    simulated_timestamp = timestamp_utc or datetime.now(timezone.utc).isoformat()
    evaluated_events = raw_events[:safe_limit]
    truncated_events_count = max(0, len(raw_events) - len(evaluated_events))

    rejection_counter: Counter[str] = Counter()
    redaction_failures: list[dict[str, Any]] = []
    subsystem_breakdown: dict[str, dict[str, int]] = {}
    event_results: list[dict[str, Any]] = []
    accepted_storage_bytes = 0
    accepted_count = 0
    rejected_count = 0

    for index, raw_event in enumerate(evaluated_events):
        normalized = normalize_runtime_event(raw_event)
        subsystem = str(normalized.get("subsystem") or "UNKNOWN")
        breakdown = subsystem_breakdown.setdefault(
            subsystem,
            {"total": 0, "accepted": 0, "rejected": 0},
        )
        breakdown["total"] += 1

        redaction_paths = _unredacted_sensitive_paths(raw_event)
        approval = validate_persistence_request(
            requested_subsystems=[subsystem],
            requested_window_minutes=requested_window_minutes,
            reason=reason,
            operator_id=operator_id,
            approval_token="SIMULATED_APPROVAL_TOKEN"
            if approval_token_present
            else "",
            requested_export_format=requested_export_format,
            policy=persistence_policy,
            timestamp_utc=simulated_timestamp,
        )
        reasons = list(approval.get("blocking_reasons", []))

        if retention_policy.redaction_required and redaction_paths:
            reasons.append("REDACTION_REQUIRED")
            redaction_failures.append(
                {
                    "event_id": str(normalized.get("event_id") or ""),
                    "subsystem": subsystem,
                    "event_type": str(normalized.get("event_type") or ""),
                    "paths": redaction_paths,
                }
            )
        if (
            retention_policy.redaction_required
            and str(normalized.get("redaction_status") or "")
            != RUNTIME_EVENT_REDACTION_STATUS
        ):
            reasons.append("REDACTION_STATUS_UNSAFE")

        if reasons:
            rejected_count += 1
            breakdown["rejected"] += 1
            rejection_counter.update(reasons)
        else:
            accepted_count += 1
            breakdown["accepted"] += 1
            accepted_storage_bytes += len(safe_json_dumps(normalized).encode("utf-8"))

        event_results.append(
            {
                "index": index,
                "event_id": str(normalized.get("event_id") or ""),
                "correlation_id": str(normalized.get("correlation_id") or ""),
                "event_type": str(normalized.get("event_type") or ""),
                "subsystem": subsystem,
                "accepted": not reasons,
                "rejection_reasons": reasons,
            }
        )

    if truncated_events_count:
        rejection_counter["EXPORT_LIMIT_EXCEEDED"] += truncated_events_count
        rejected_count += truncated_events_count

    return RuntimeEventPersistenceSimulationResult(
        simulation_id=_simulation_id(
            {
                "timestamp_utc": simulated_timestamp,
                "event_count": len(raw_events),
                "limit": safe_limit,
                "operator_id": operator_id,
            }
        ),
        accepted_events_count=accepted_count,
        rejected_events_count=rejected_count,
        rejection_reasons=dict(sorted(rejection_counter.items())),
        redaction_failures=redaction_failures,
        estimated_storage_bytes=accepted_storage_bytes,
        estimated_event_rate=_event_rate(len(evaluated_events), requested_window_minutes),
        subsystem_breakdown=subsystem_breakdown,
        simulated_timestamp=simulated_timestamp,
        inspected_events_count=len(raw_events),
        truncated_events_count=truncated_events_count,
        evaluated_events_count=len(evaluated_events),
        event_results=event_results,
        persistence_enabled=False,
        writes_performed=False,
        simulation_only=True,
        read_only=True,
        retention_policy=retention_policy.as_dict(),
        persistence_policy=persistence_policy.as_dict(),
    ).as_dict()


def get_runtime_event_persistence_simulation_payload(
    event_bus: RuntimeEventBus | None = None,
    *,
    event_type: str = "",
    subsystem: str = "",
    severity: str = "",
    correlation_id: str = "",
    limit: int | None = None,
    requested_window_minutes: int = 15,
    reason: str = "runtime event persistence dry-run simulation",
    operator_id: str = "",
    approval_token_present: bool = False,
    requested_export_format: str = "json",
    retention_policy: RuntimeEventRetentionPolicy = DEFAULT_RUNTIME_EVENT_RETENTION_POLICY,
    persistence_policy: RuntimeEventPersistencePolicy = DEFAULT_RUNTIME_EVENT_PERSISTENCE_POLICY,
) -> dict[str, Any]:
    safe_limit = _safe_limit(limit, retention_policy)
    events: tuple[dict[str, Any], ...]
    if event_bus is None:
        events = ()
    else:
        events = event_bus.get_recent(
            max(0, int(retention_policy.max_events or 0)),
            subsystem=subsystem,
            event_type=event_type,
            severity=severity,
        )
    filtered = _filter_by_correlation(events, correlation_id)

    payload = simulate_runtime_event_persistence(
        filtered,
        retention_policy=retention_policy,
        persistence_policy=persistence_policy,
        limit=safe_limit,
        requested_window_minutes=requested_window_minutes,
        reason=reason,
        operator_id=operator_id,
        approval_token_present=approval_token_present,
        requested_export_format=requested_export_format,
    )
    payload["filters"] = {
        "event_type": str(event_type or ""),
        "subsystem": str(subsystem or ""),
        "severity": str(severity or ""),
        "correlation_id": str(correlation_id or ""),
        "limit": safe_limit,
        "requested_window_minutes": requested_window_minutes,
        "requested_export_format": str(requested_export_format or "json"),
        "approval_token_present": bool(approval_token_present),
    }
    payload["source"] = "runtime_event_bus"
    payload["bus_available"] = event_bus is not None
    return payload


def _safe_limit(
    value: int | None,
    policy: RuntimeEventRetentionPolicy,
) -> int:
    try:
        parsed = int(value) if value is not None else int(policy.default_inspection_limit)
    except Exception:
        parsed = int(policy.default_inspection_limit)
    max_scan = max(0, int(policy.max_events or 0))
    max_export = max(0, int(policy.max_export_limit or 0))
    max_allowed = min(max_scan, max_export) if max_scan and max_export else max(max_scan, max_export)
    return max(0, min(parsed, max_allowed))


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


def _unredacted_sensitive_paths(value: Any, *, prefix: str = "") -> list[str]:
    failures: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if _is_sensitive_key(str(key)) and _is_unredacted_value(item):
                failures.append(path)
            failures.extend(_unredacted_sensitive_paths(item, prefix=path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            failures.extend(
                _unredacted_sensitive_paths(item, prefix=f"{prefix}[{index}]")
            )
    return failures


def _is_sensitive_key(key: str) -> bool:
    normalized = key.strip().lower()
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def _is_unredacted_value(value: Any) -> bool:
    if value in (None, "", "REDACTED"):
        return False
    if isinstance(value, (Mapping, list, tuple)):
        return False
    return True


def _event_rate(event_count: int, requested_window_minutes: int) -> float:
    try:
        window = int(requested_window_minutes)
    except Exception:
        window = 0
    if window <= 0:
        return 0.0
    return round(float(event_count) / float(window), 6)


def _simulation_id(payload: Mapping[str, Any]) -> str:
    serialized = safe_json_dumps(payload)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:20].upper()
    return f"EVSIM-{digest}"


__all__ = [
    "RUNTIME_EVENT_PERSISTENCE_SIMULATOR_VERSION",
    "RuntimeEventPersistenceSimulationResult",
    "get_runtime_event_persistence_simulation_payload",
    "simulate_runtime_event_persistence",
]
