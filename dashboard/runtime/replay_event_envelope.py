from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from dashboard.runtime.replay_correlation import (
    create_correlation_id,
    create_lifecycle_id,
)


REPLAY_EVENT_ENVELOPE_SCHEMA_VERSION = "css.replay_event_envelope.v1"
REDACTION_STATUS_REDACTED = "redacted"
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
class ReplayEventEnvelope:
    schema_version: str
    correlation_id: str
    event_id: str
    parent_event_id: str
    event_type: str
    subsystem: str
    timestamp_utc: str
    broker: str
    broker_mode: str
    engine_mode: str
    symbol: str
    asset_class: str
    cycle: str
    payload: dict[str, Any]
    redaction_status: str = REDACTION_STATUS_REDACTED
    source_module: str = ""
    lifecycle_id: str = ""

    def as_dict(self) -> dict[str, Any]:
        return _json_safe(asdict(self))


def build_replay_event_envelope(
    payload: Mapping[str, Any],
    *,
    subsystem: str,
    source_module: str,
    parent_event_id: str = "",
    correlation_id: str = "",
    lifecycle_id: str = "",
) -> dict[str, Any]:
    safe_payload = _json_safe(payload)
    lifecycle = str(lifecycle_id or create_lifecycle_id(safe_payload))
    correlation = str(correlation_id or safe_payload.get("correlation_id") or "")
    if not correlation:
        correlation = create_correlation_id(
            session_id=safe_payload.get("session_id"),
            lifecycle_id=lifecycle,
            position_id=safe_payload.get("position_id"),
            symbol=safe_payload.get("symbol"),
            asset_class=safe_payload.get("asset_class"),
            cycle=safe_payload.get("cycle"),
        )

    timestamp = str(
        safe_payload.get("timestamp_utc")
        or safe_payload.get("persisted_utc")
        or datetime.now(timezone.utc).isoformat()
    )
    event_type = str(safe_payload.get("event_type") or "unknown_replay_event")
    event_id = str(safe_payload.get("event_id") or "")
    if not event_id:
        event_id = _event_id(
            {
                "correlation_id": correlation,
                "event_type": event_type,
                "timestamp_utc": timestamp,
                "payload": safe_payload,
            }
        )

    return ReplayEventEnvelope(
        schema_version=REPLAY_EVENT_ENVELOPE_SCHEMA_VERSION,
        correlation_id=correlation,
        lifecycle_id=lifecycle,
        event_id=event_id,
        parent_event_id=str(parent_event_id or safe_payload.get("parent_event_id") or ""),
        event_type=event_type,
        subsystem=str(subsystem or safe_payload.get("subsystem") or "unknown"),
        timestamp_utc=timestamp,
        broker=str(safe_payload.get("broker", "")),
        broker_mode=str(safe_payload.get("broker_mode") or safe_payload.get("mode") or ""),
        engine_mode=str(safe_payload.get("engine_mode", "")),
        symbol=str(safe_payload.get("symbol", "")),
        asset_class=str(safe_payload.get("asset_class", "")),
        cycle=str(safe_payload.get("cycle", "")),
        payload=safe_payload,
        source_module=str(source_module or ""),
    ).as_dict()


def is_replay_event_envelope(value: Mapping[str, Any]) -> bool:
    return str(value.get("schema_version", "")).startswith(
        "css.replay_event_envelope."
    ) and ("redaction_status" in value or "source_module" in value)


def _event_id(payload: Mapping[str, Any]) -> str:
    serialized = json_dump_stable(payload)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:20].upper()


def json_dump_stable(payload: Mapping[str, Any]) -> str:
    return str(
        __import__("json").dumps(
            _json_safe(payload),
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
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
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    return value


def _is_sensitive_key(key: str) -> bool:
    normalized = key.strip().lower()
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


__all__ = [
    "REDACTION_STATUS_REDACTED",
    "REPLAY_EVENT_ENVELOPE_SCHEMA_VERSION",
    "ReplayEventEnvelope",
    "build_replay_event_envelope",
    "is_replay_event_envelope",
]
