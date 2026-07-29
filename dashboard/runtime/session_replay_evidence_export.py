"""Read-only session replay evidence projection."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

SESSION_REPLAY_EVIDENCE_EXPORT_VERSION = "css.session_replay_evidence_export.v2"

_SAFETY_DISCLAIMER = (
    "Session replay evidence export is additive review metadata only. It does not "
    "write archives, approve trading, arm execution, place orders, or mutate broker state."
)
_REQUIRED_EVENT_FIELDS = ("event_id", "correlation_id", "event_type", "timestamp_utc")


def build_session_replay_evidence_export_payload(
    *,
    replay_correlation_ids: Sequence[str] | None = None,
    replay_path: str | None = None,
    session_id: str = "",
    governance_event_count: int = 0,
    generated_at_utc: str = "",
    replay_events: Sequence[Mapping[str, Any]] | None = None,
    audit_events: Sequence[Mapping[str, Any]] | None = None,
    execution_history: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    requested_ids = _string_list(replay_correlation_ids)
    normalized_events, event_blockers = _normalize_replay_events(replay_events)
    normalized_audit, audit_blockers = _normalize_audit_events(audit_events)
    normalized_execution, execution_blockers = _normalize_execution_history(
        execution_history
    )
    duplicate_ids = _duplicate_event_ids(normalized_events)
    missing_ids = [
        item for item in requested_ids if item.upper() not in _known_correlation_ids(normalized_events)
    ]
    blockers = (
        event_blockers
        + audit_blockers
        + execution_blockers
        + [f"duplicate_event_id:{item}" for item in duplicate_ids]
    )
    if not _text(session_id):
        blockers.append("session_id_missing")
    if missing_ids:
        blockers.append("requested_replay_correlation_missing")
    if not normalized_events:
        blockers.append("replay_events_missing")

    matched_ids = [
        item for item in requested_ids if item.upper() in _known_correlation_ids(normalized_events)
    ]
    evidence_complete = bool(normalized_events) and not blockers

    return {
        "payload_version": SESSION_REPLAY_EVIDENCE_EXPORT_VERSION,
        "generated_at_utc": generated_at_utc or _utc_now(),
        "session_id": _text(session_id),
        "status": "OK" if evidence_complete else "DATA_UNAVAILABLE",
        "readiness_status": "READY" if evidence_complete else "BLOCKED",
        "replay_sink_path": _text(replay_path),
        "replay_correlation_ids": requested_ids,
        "matched_replay_correlation_ids": matched_ids,
        "missing_replay_correlation_ids": missing_ids,
        "replay_event_count": len(normalized_events),
        "unique_replay_event_count": len(normalized_events) - len(duplicate_ids),
        "duplicate_replay_event_count": len(duplicate_ids),
        "duplicate_replay_event_ids": duplicate_ids,
        "malformed_replay_event_count": len(event_blockers),
        "malformed_audit_event_count": len(audit_blockers),
        "malformed_execution_history_count": len(execution_blockers),
        "malformed_replay_lines": 0,
        "governance_event_count": _safe_count(governance_event_count),
        "audit_event_count": len(normalized_audit),
        "execution_history_count": len(normalized_execution),
        "evidence_complete": evidence_complete,
        "trade_lifecycle_replay_summary": _summary(normalized_events),
        "trade_lifecycle_replay_events": normalized_events[:25],
        "audit_events": normalized_audit[:25],
        "execution_history": normalized_execution[:25],
        "authority_blockers": blockers,
        "warnings": _warnings(requested_ids, missing_ids, normalized_events, blockers),
        "safety_disclaimer": _SAFETY_DISCLAIMER,
        "trading_armed": False,
        "execution_allowed": False,
        "broker_mutation_allowed": False,
        "persistence_enabled": False,
        "orders_enabled": False,
        "source_metadata": {
            "source": "dashboard.runtime.session_replay_evidence_export",
            "canonical_input": "dashboard.runtime.replay_event_envelope.ReplayEventEnvelope",
            "read_only": True,
            "projection_only": True,
            "export_only": True,
            "additive": True,
            "replay_path_ignored": bool(replay_path),
            "no_broker_calls": True,
            "no_environment_reads": True,
            "no_filesystem_reads": True,
            "no_filesystem_writes": True,
            "no_order_placement": True,
            "frontend_safe": True,
        },
    }


def _normalize_replay_events(
    replay_events: Sequence[Mapping[str, Any]] | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    normalized: list[dict[str, Any]] = []
    blockers: list[str] = []
    for index, event in enumerate(replay_events or ()):
        if not isinstance(event, Mapping):
            blockers.append(f"replay_event_{index}_malformed")
            continue
        missing = [field for field in _REQUIRED_EVENT_FIELDS if not _text(event.get(field))]
        if missing:
            blockers.append(f"replay_event_{index}_missing_{missing[0]}")
            continue
        order_id = _text(event.get("order_id"))
        if "order" in _text(event.get("event_type")).lower() and not order_id:
            blockers.append(f"replay_event_{index}_missing_order_id")
            continue
        normalized.append(
            {
                "schema_version": _text(event.get("schema_version")) or "UNKNOWN",
                "event_id": _text(event.get("event_id")),
                "correlation_id": _text(event.get("correlation_id")).upper(),
                "session_id": _text(event.get("session_id")),
                "order_id": order_id,
                "parent_event_id": _text(event.get("parent_event_id")),
                "event_type": _text(event.get("event_type")),
                "subsystem": _text(event.get("subsystem")),
                "timestamp_utc": _text(event.get("timestamp_utc")),
                "position_id": _text(event.get("position_id")),
                "symbol": _text(event.get("symbol")).upper(),
                "asset_class": _text(event.get("asset_class")).upper(),
                "broker": _text(event.get("broker")).upper(),
                "broker_mode": _text(event.get("broker_mode")).upper(),
                "engine_mode": _text(event.get("engine_mode")).upper(),
                "cycle": _text(event.get("cycle")),
                "payload": _safe_mapping(event.get("payload")),
            }
        )
    normalized.sort(
        key=lambda item: (
            item["timestamp_utc"],
            item["correlation_id"],
            item["event_id"],
            item["event_type"],
        )
    )
    return normalized, blockers


def _normalize_audit_events(
    audit_events: Sequence[Mapping[str, Any]] | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    normalized: list[dict[str, Any]] = []
    blockers: list[str] = []
    for index, event in enumerate(audit_events or ()):
        if not isinstance(event, Mapping):
            blockers.append(f"audit_event_{index}_malformed")
            continue
        event_id = _text(event.get("event_id"))
        timestamp = _text(event.get("timestamp_utc") or event.get("timestamp"))
        if not event_id or not timestamp:
            blockers.append(f"audit_event_{index}_missing_id_or_timestamp")
            continue
        normalized.append(
            {
                "event_id": event_id,
                "timestamp_utc": timestamp,
                "event_type": _text(event.get("event_type")),
                "correlation_id": _text(event.get("correlation_id")).upper(),
                "session_id": _text(event.get("session_id")),
            }
        )
    normalized.sort(key=lambda item: (item["timestamp_utc"], item["event_id"]))
    return normalized, blockers


def _normalize_execution_history(
    execution_history: Sequence[Mapping[str, Any]] | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    normalized: list[dict[str, Any]] = []
    blockers: list[str] = []
    for index, item in enumerate(execution_history or ()):
        if not isinstance(item, Mapping):
            blockers.append(f"execution_history_{index}_malformed")
            continue
        event_id = _text(item.get("event_id") or item.get("execution_id"))
        timestamp = _text(item.get("timestamp_utc") or item.get("timestamp"))
        if not event_id or not timestamp:
            blockers.append(f"execution_history_{index}_missing_id_or_timestamp")
            continue
        normalized.append(
            {
                "event_id": event_id,
                "timestamp_utc": timestamp,
                "correlation_id": _text(item.get("correlation_id")).upper(),
                "session_id": _text(item.get("session_id")),
                "order_id": _text(item.get("order_id")),
                "execution_state": _text(item.get("execution_state")).upper(),
                "order_mutation_allowed": False,
            }
        )
    normalized.sort(key=lambda item: (item["timestamp_utc"], item["event_id"]))
    return normalized, blockers


def _summary(events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "total_events": len(events),
        "by_event_type": {},
        "by_asset_class": {},
        "by_symbol": {},
        "by_subsystem": {},
        "by_correlation_id": {},
    }
    for event in events:
        _increment(summary["by_event_type"], _text(event.get("event_type")) or "UNKNOWN")
        _increment(summary["by_asset_class"], _text(event.get("asset_class")) or "UNKNOWN")
        _increment(summary["by_symbol"], _text(event.get("symbol")) or "UNKNOWN")
        _increment(summary["by_subsystem"], _text(event.get("subsystem")) or "UNKNOWN")
        _increment(
            summary["by_correlation_id"],
            _text(event.get("correlation_id")) or "UNKNOWN",
        )
    return summary


def _duplicate_event_ids(events: Sequence[Mapping[str, Any]]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for event in events:
        event_id = _text(event.get("event_id"))
        if event_id in seen and event_id not in duplicates:
            duplicates.append(event_id)
        seen.add(event_id)
    return sorted(duplicates)


def _known_correlation_ids(events: Sequence[Mapping[str, Any]]) -> set[str]:
    return {_text(event.get("correlation_id")).upper() for event in events if _text(event.get("correlation_id"))}


def _warnings(
    requested_ids: list[str],
    missing_ids: list[str],
    events: Sequence[Mapping[str, Any]],
    blockers: Sequence[str],
) -> list[str]:
    warnings: list[str] = []
    if not events:
        warnings.append("REPLAY_EVENTS_NOT_SUPPLIED")
    if requested_ids and missing_ids:
        warnings.append("REPLAY_CORRELATION_NOT_IN_SUPPLIED_EVENTS")
    if not requested_ids:
        warnings.append("REPLAY_CORRELATION_IDS_NOT_SUPPLIED")
    if blockers:
        warnings.append("SESSION_REPLAY_EVIDENCE_FAIL_CLOSED")
    return warnings


def _increment(target: dict[str, int], key: str) -> None:
    target[key] = int(target.get(key, 0)) + 1


def _string_list(value: Sequence[str] | None) -> list[str]:
    if not value:
        return []
    return sorted({str(item).strip().upper() for item in value if str(item).strip()})


def _safe_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_count(value: Any) -> int:
    try:
        count = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, count)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "SESSION_REPLAY_EVIDENCE_EXPORT_VERSION",
    "build_session_replay_evidence_export_payload",
]
