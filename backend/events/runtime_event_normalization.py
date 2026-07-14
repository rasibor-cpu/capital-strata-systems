from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from dashboard.runtime.evidence_hashing import hash_evidence_payload


RUNTIME_EVENT_SCHEMA_VERSION = "css.runtime_event.normalized.v1"
RUNTIME_EVENT_HASH_SOURCE_TYPE = "runtime_event_normalization"
RUNTIME_EVENT_REDACTION_STATUS = "redacted"

_ALLOWED_SEVERITIES = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
_SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "credential",
    "password",
    "pem",
    "private",
    "secret",
    "token",
)
_SENSITIVE_VALUE_MARKERS = (
    "api_key=",
    "apikey=",
    "authorization:",
    "bearer ",
    "password=",
    "private key",
    "secret=",
    "token=",
)
_PUBLIC_SAFETY_KEYS = {
    "broker_mutation_allowed",
    "execution_allowed",
    "mutation_allowed",
    "order_submit_allowed",
    "persistence_enabled",
    "redaction_required",
    "trading_armed",
}


class RuntimeEventValidationError(ValueError):
    """Raised when a runtime event cannot satisfy the canonical schema."""


@dataclass(frozen=True)
class NormalizedRuntimeEvent:
    schema_version: str
    event_id: str
    event_type: str
    event_category: str
    event_severity: str
    event_source: str
    timestamp_utc: str
    correlation_id: str
    payload: dict[str, Any]
    metadata: dict[str, Any]
    evidence_hash: str
    evidence_hash_id: str
    evidence_algorithm: str
    redaction_status: str = RUNTIME_EVENT_REDACTION_STATUS

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_runtime_event(
    event: Mapping[str, Any] | NormalizedRuntimeEvent,
    *,
    timestamp_utc: str = "",
    correlation_id: str = "",
    event_id: str = "",
    evidence_hash: str | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build the canonical runtime event envelope.

    This module is a normalization and audit utility only. It does not publish,
    persist, route, execute, or mutate trading state.
    """

    if isinstance(event, NormalizedRuntimeEvent):
        record = event.as_dict()
        validate_runtime_event(record)
        return record

    if not isinstance(event, Mapping):
        raise RuntimeEventValidationError("event must be a mapping")

    payload = _extract_payload(event)
    metadata = _extract_metadata(event)
    normalized_timestamp = _timestamp(
        timestamp_utc
        or str(event.get("timestamp_utc") or event.get("timestamp") or "")
    )
    normalized_correlation = str(
        correlation_id or event.get("correlation_id") or ""
    ).strip()
    normalized_type = _required_text(
        event.get("event_type") or event.get("message_type") or "runtime_event",
        "event_type",
    )
    normalized_category = _required_text(
        event.get("event_category")
        or event.get("category")
        or event.get("subsystem")
        or "runtime",
        "event_category",
    )
    normalized_source = _required_text(
        event.get("event_source") or event.get("source") or event.get("source_module"),
        "event_source",
    )
    normalized_severity = _normalize_severity(
        event.get("event_severity") or event.get("severity") or "INFO"
    )
    evidence = _resolve_evidence_hash(
        event_type=normalized_type,
        event_category=normalized_category,
        event_severity=normalized_severity,
        event_source=normalized_source,
        correlation_id=normalized_correlation,
        payload=payload,
        metadata=metadata,
        evidence_hash=evidence_hash or event.get("evidence_hash"),
    )
    normalized_event_id = str(event_id or event.get("event_id") or "").strip()
    if not normalized_event_id:
        normalized_event_id = _event_id(
            {
                "timestamp_utc": normalized_timestamp,
                "event_type": normalized_type,
                "event_category": normalized_category,
                "event_source": normalized_source,
                "correlation_id": normalized_correlation,
                "evidence_hash": evidence["evidence_hash"],
            }
        )

    record = NormalizedRuntimeEvent(
        schema_version=RUNTIME_EVENT_SCHEMA_VERSION,
        event_id=normalized_event_id,
        event_type=normalized_type,
        event_category=normalized_category,
        event_severity=normalized_severity,
        event_source=normalized_source,
        timestamp_utc=normalized_timestamp,
        correlation_id=normalized_correlation,
        payload=payload,
        metadata=metadata,
        evidence_hash=str(evidence["evidence_hash"]),
        evidence_hash_id=str(evidence["evidence_hash_id"]),
        evidence_algorithm=str(evidence["algorithm"]),
    ).as_dict()
    validate_runtime_event(record)
    return record


def validate_runtime_event(event: Mapping[str, Any]) -> None:
    missing = [
        field
        for field in (
            "schema_version",
            "event_id",
            "event_type",
            "event_category",
            "event_severity",
            "event_source",
            "timestamp_utc",
            "correlation_id",
            "payload",
            "metadata",
            "evidence_hash",
            "evidence_hash_id",
            "evidence_algorithm",
            "redaction_status",
        )
        if field not in event
    ]
    if missing:
        raise RuntimeEventValidationError(
            f"Missing required runtime event fields: {', '.join(missing)}"
        )
    if event.get("schema_version") != RUNTIME_EVENT_SCHEMA_VERSION:
        raise RuntimeEventValidationError("Unsupported runtime event schema version")
    if event.get("evidence_algorithm") != "sha256":
        raise RuntimeEventValidationError("Unsupported evidence algorithm")
    if event.get("redaction_status") != RUNTIME_EVENT_REDACTION_STATUS:
        raise RuntimeEventValidationError("Unsafe runtime event redaction status")
    if not isinstance(event.get("payload"), Mapping):
        raise RuntimeEventValidationError("payload must be a mapping")
    if not isinstance(event.get("metadata"), Mapping):
        raise RuntimeEventValidationError("metadata must be a mapping")
    _required_text(event.get("event_id"), "event_id")
    _required_text(event.get("event_type"), "event_type")
    _required_text(event.get("event_category"), "event_category")
    _required_text(event.get("event_source"), "event_source")
    if str(event.get("event_severity") or "").upper() not in _ALLOWED_SEVERITIES:
        raise RuntimeEventValidationError("Unsupported event severity")
    _parse_timestamp(str(event.get("timestamp_utc") or ""))


def canonical_runtime_event_json(event: Mapping[str, Any]) -> str:
    validate_runtime_event(event)
    return _canonical_json(event)


def stable_runtime_event_evidence_payload(
    event: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": RUNTIME_EVENT_SCHEMA_VERSION,
        "event_type": _required_text(event.get("event_type"), "event_type"),
        "event_category": _required_text(
            event.get("event_category"), "event_category"
        ),
        "event_severity": _normalize_severity(event.get("event_severity")),
        "event_source": _required_text(event.get("event_source"), "event_source"),
        "correlation_id": str(event.get("correlation_id") or "").strip(),
        "payload": _json_safe(event.get("payload") or {}),
        "metadata": _json_safe(event.get("metadata") or {}),
    }


def runtime_event_evidence_hash(event: Mapping[str, Any]) -> dict[str, Any]:
    payload = stable_runtime_event_evidence_payload(event)
    return hash_evidence_payload(
        payload,
        source_type=RUNTIME_EVENT_HASH_SOURCE_TYPE,
        source_reference=str(event.get("correlation_id") or event.get("event_type") or ""),
    )


def runtime_event_journal_metadata(event: Mapping[str, Any]) -> dict[str, Any]:
    validate_runtime_event(event)
    return {
        "runtime_event_schema_version": str(event["schema_version"]),
        "runtime_event_id": str(event["event_id"]),
        "runtime_event_type": str(event["event_type"]),
        "runtime_event_category": str(event["event_category"]),
        "runtime_event_severity": str(event["event_severity"]),
        "runtime_event_source": str(event["event_source"]),
        "runtime_event_timestamp_utc": str(event["timestamp_utc"]),
        "runtime_event_correlation_id": str(event["correlation_id"]),
        "runtime_event_evidence_hash": str(event["evidence_hash"]),
    }


def runtime_event_order_key(event: Mapping[str, Any]) -> tuple[str, str]:
    validate_runtime_event(event)
    return (str(event["timestamp_utc"]), str(event["event_id"]))


def order_runtime_events(events: Iterable[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    normalized = [normalize_runtime_event(event) for event in events]
    return tuple(sorted(normalized, key=runtime_event_order_key))


def _extract_payload(event: Mapping[str, Any]) -> dict[str, Any]:
    payload = event.get("payload")
    if payload is None:
        payload = event.get("data", {})
    if not isinstance(payload, Mapping):
        raise RuntimeEventValidationError("payload must be a mapping")
    return _json_safe(payload)


def _extract_metadata(event: Mapping[str, Any]) -> dict[str, Any]:
    metadata = event.get("metadata", {})
    if not isinstance(metadata, Mapping):
        raise RuntimeEventValidationError("metadata must be a mapping")
    return _json_safe(metadata)


def _resolve_evidence_hash(
    *,
    event_type: str,
    event_category: str,
    event_severity: str,
    event_source: str,
    correlation_id: str,
    payload: Mapping[str, Any],
    metadata: Mapping[str, Any],
    evidence_hash: str | Mapping[str, Any] | None,
) -> dict[str, Any]:
    if isinstance(evidence_hash, Mapping):
        required = ("evidence_hash", "evidence_hash_id", "algorithm")
        if all(key in evidence_hash for key in required):
            return {
                "evidence_hash": str(evidence_hash["evidence_hash"]),
                "evidence_hash_id": str(evidence_hash["evidence_hash_id"]),
                "algorithm": str(evidence_hash["algorithm"]),
            }
    if isinstance(evidence_hash, str) and evidence_hash.strip():
        text = evidence_hash.strip()
        return {
            "evidence_hash": text,
            "evidence_hash_id": f"EVHASH-{text[:20].upper()}",
            "algorithm": "sha256",
        }
    stable_payload = stable_runtime_event_evidence_payload(
        {
            "event_type": event_type,
            "event_category": event_category,
            "event_severity": event_severity,
            "event_source": event_source,
            "correlation_id": correlation_id,
            "payload": payload,
            "metadata": metadata,
        }
    )
    return hash_evidence_payload(
        stable_payload,
        source_type=RUNTIME_EVENT_HASH_SOURCE_TYPE,
        source_reference=str(correlation_id or event_type),
    )


def _timestamp(value: str = "") -> str:
    text = str(value or "").strip()
    if text:
        return _format_utc(_parse_timestamp(text))
    return _format_utc(datetime.now(timezone.utc))


def _parse_timestamp(value: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise RuntimeEventValidationError("timestamp_utc is required")
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except Exception as exc:
        raise RuntimeEventValidationError("timestamp_utc must be ISO-8601") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _normalize_severity(value: Any) -> str:
    severity = str(value or "INFO").strip().upper()
    if severity not in _ALLOWED_SEVERITIES:
        raise RuntimeEventValidationError("Unsupported event severity")
    return severity


def _required_text(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise RuntimeEventValidationError(f"{field_name} is required")
    return text


def _event_id(payload: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"RTEVT-{digest[:20].upper()}"


def _canonical_json(value: Any) -> str:
    return json.dumps(
        _json_safe(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): (
                "REDACTED" if _is_sensitive_key(str(key)) else _json_safe(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (datetime, Path)):
        return str(value)
    if isinstance(value, str) and _contains_sensitive_marker(value):
        return "REDACTED"
    return value


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower().replace("-", "_")
    if lowered in _PUBLIC_SAFETY_KEYS:
        return False
    return any(part in lowered for part in _SENSITIVE_KEY_PARTS)


def _contains_sensitive_marker(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in _SENSITIVE_VALUE_MARKERS)


__all__ = [
    "RUNTIME_EVENT_HASH_SOURCE_TYPE",
    "RUNTIME_EVENT_REDACTION_STATUS",
    "RUNTIME_EVENT_SCHEMA_VERSION",
    "NormalizedRuntimeEvent",
    "RuntimeEventValidationError",
    "canonical_runtime_event_json",
    "normalize_runtime_event",
    "order_runtime_events",
    "runtime_event_evidence_hash",
    "runtime_event_journal_metadata",
    "runtime_event_order_key",
    "stable_runtime_event_evidence_payload",
    "validate_runtime_event",
]
