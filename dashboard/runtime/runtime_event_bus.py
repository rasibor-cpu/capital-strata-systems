from __future__ import annotations

import hashlib
import json
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from threading import RLock
from typing import Any

from dashboard.runtime.replay_correlation import correlation_key
from dashboard.runtime.replay_event_envelope import build_replay_event_envelope


RUNTIME_EVENT_BUS_VERSION = "css.runtime_event_bus.v1"
RUNTIME_EVENT_SCHEMA_VERSION = "css.runtime_event.v1"
RUNTIME_EVENT_REDACTION_STATUS = "redacted"
RuntimeEventHandler = Callable[[dict[str, Any]], None]

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
_SEVERITIES = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


@dataclass(frozen=True)
class RuntimeEvent:
    event_id: str
    correlation_id: str
    event_type: str
    subsystem: str
    timestamp_utc: str
    severity: str
    source_module: str
    payload: dict[str, Any]
    schema_version: str = RUNTIME_EVENT_SCHEMA_VERSION
    redaction_status: str = RUNTIME_EVENT_REDACTION_STATUS

    def as_dict(self) -> dict[str, Any]:
        return _json_safe(asdict(self))


@dataclass(frozen=True)
class RuntimeEventSubscription:
    subscription_id: str
    subsystem: str
    event_type: str
    handler: RuntimeEventHandler | None = None

    def matches(self, event: Mapping[str, Any]) -> bool:
        if self.subsystem and str(event.get("subsystem", "")).lower() != self.subsystem:
            return False
        if self.event_type and str(event.get("event_type", "")).lower() != self.event_type:
            return False
        return True


class RuntimeEventBus:
    def __init__(
        self,
        *,
        max_recent: int = 1000,
        logger: Callable[[str], None] | None = None,
    ) -> None:
        self._events: deque[dict[str, Any]] = deque(maxlen=max(1, int(max_recent or 1)))
        self._subscriptions: dict[str, RuntimeEventSubscription] = {}
        self._lock = RLock()
        self._logger = logger

    def publish(self, event: RuntimeEvent | Mapping[str, Any]) -> dict[str, Any]:
        normalized = normalize_runtime_event(event)
        handlers: list[RuntimeEventHandler] = []

        with self._lock:
            self._events.append(normalized)
            handlers = [
                subscription.handler
                for subscription in self._subscriptions.values()
                if subscription.handler is not None and subscription.matches(normalized)
            ]

        for handler in handlers:
            try:
                handler(dict(normalized))
            except Exception as exc:
                self._log(f"[EVENT BUS WARN] subscriber failed: {str(exc)[:80]}")

        return normalized

    def subscribe(
        self,
        subsystem: str = "",
        event_type: str = "",
        handler: RuntimeEventHandler | None = None,
    ) -> str:
        parsed_subsystem, parsed_event_type = _parse_subscription_filter(
            subsystem,
            event_type,
        )
        subscription_id = _event_id(
            {
                "subsystem": parsed_subsystem,
                "event_type": parsed_event_type,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "count": len(self._subscriptions),
            },
            prefix="SUB",
        )
        subscription = RuntimeEventSubscription(
            subscription_id=subscription_id,
            subsystem=parsed_subsystem,
            event_type=parsed_event_type,
            handler=handler,
        )
        with self._lock:
            self._subscriptions[subscription_id] = subscription
        return subscription_id

    def unsubscribe(self, subscription_id: str) -> bool:
        with self._lock:
            return self._subscriptions.pop(str(subscription_id), None) is not None

    def get_recent(
        self,
        limit: int = 100,
        *,
        subsystem: str = "",
        event_type: str = "",
        severity: str = "",
    ) -> tuple[dict[str, Any], ...]:
        subsystem_filter, event_type_filter = _parse_subscription_filter(
            subsystem,
            event_type,
        )
        severity_filter = _normalize_filter(severity).upper()
        safe_limit = max(0, int(limit or 0))

        with self._lock:
            events = list(self._events)

        filtered: list[dict[str, Any]] = []
        for event in events:
            if subsystem_filter and str(event.get("subsystem", "")).lower() != subsystem_filter:
                continue
            if event_type_filter and str(event.get("event_type", "")).lower() != event_type_filter:
                continue
            if severity_filter and str(event.get("severity", "")).upper() != severity_filter:
                continue
            filtered.append(dict(event))

        return tuple(filtered[-safe_limit:]) if safe_limit else ()

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
            self._subscriptions.clear()

    def subscription_count(self) -> int:
        with self._lock:
            return len(self._subscriptions)

    def _log(self, message: str) -> None:
        if self._logger is not None:
            self._logger(message)


def build_runtime_event(
    payload: Mapping[str, Any] | None = None,
    *,
    event_type: str = "",
    subsystem: str = "",
    severity: str = "INFO",
    source_module: str = "",
    correlation_id: str = "",
    timestamp_utc: str = "",
    event_id: str = "",
) -> dict[str, Any]:
    safe_payload = _json_safe(payload or {})
    normalized_event_type = str(
        event_type
        or safe_payload.get("event_type")
        or safe_payload.get("message_type")
        or "runtime_event"
    )
    normalized_subsystem = str(
        subsystem
        or safe_payload.get("subsystem")
        or safe_payload.get("section")
        or safe_payload.get("category")
        or "runtime"
    )
    timestamp = str(
        timestamp_utc
        or safe_payload.get("timestamp_utc")
        or safe_payload.get("generated_utc")
        or safe_payload.get("generated_at")
        or datetime.now(timezone.utc).isoformat()
    )
    correlation = str(
        correlation_id
        or safe_payload.get("correlation_id")
        or correlation_key(safe_payload)
    )
    runtime_event = RuntimeEvent(
        event_id=str(
            event_id
            or safe_payload.get("event_id")
            or _event_id(
                {
                    "correlation_id": correlation,
                    "event_type": normalized_event_type,
                    "subsystem": normalized_subsystem,
                    "timestamp_utc": timestamp,
                    "payload": safe_payload,
                }
            )
        ),
        correlation_id=correlation,
        event_type=normalized_event_type,
        subsystem=normalized_subsystem,
        timestamp_utc=timestamp,
        severity=_normalize_severity(severity or safe_payload.get("severity")),
        source_module=str(source_module or safe_payload.get("source_module") or ""),
        payload=safe_payload,
    )
    return runtime_event.as_dict()


def normalize_runtime_event(event: RuntimeEvent | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(event, RuntimeEvent):
        return event.as_dict()

    if is_runtime_event(event):
        normalized = _json_safe(event)
        normalized["severity"] = _normalize_severity(normalized.get("severity"))
        normalized["redaction_status"] = RUNTIME_EVENT_REDACTION_STATUS
        return normalized

    return build_runtime_event(
        event,
        event_type=str(event.get("event_type") or event.get("message_type") or ""),
        subsystem=str(event.get("subsystem") or event.get("section") or ""),
        severity=str(event.get("severity") or "INFO"),
        source_module=str(event.get("source_module") or ""),
        correlation_id=str(event.get("correlation_id") or ""),
        timestamp_utc=str(event.get("timestamp_utc") or event.get("generated_at") or ""),
        event_id=str(event.get("event_id") or ""),
    )


def is_runtime_event(value: Mapping[str, Any]) -> bool:
    return str(value.get("schema_version", "")).startswith("css.runtime_event.")


def runtime_event_to_replay_envelope(
    event: RuntimeEvent | Mapping[str, Any],
    *,
    source_module: str = "dashboard.runtime.runtime_event_bus",
) -> dict[str, Any]:
    normalized = normalize_runtime_event(event)
    return build_replay_event_envelope(
        normalized,
        subsystem=str(normalized.get("subsystem") or "runtime"),
        source_module=str(normalized.get("source_module") or source_module),
        correlation_id=str(normalized.get("correlation_id") or ""),
    )


def runtime_event_from_replay_payload(
    payload: Mapping[str, Any],
    *,
    severity: str = "INFO",
    source_module: str = "dashboard.runtime.runtime_event_bus",
) -> dict[str, Any]:
    return build_runtime_event(
        payload,
        event_type=str(payload.get("event_type") or ""),
        subsystem=str(payload.get("subsystem") or "replay"),
        severity=severity,
        source_module=source_module,
        correlation_id=str(payload.get("correlation_id") or ""),
        timestamp_utc=str(payload.get("timestamp_utc") or payload.get("persisted_utc") or ""),
        event_id=str(payload.get("event_id") or ""),
    )


def runtime_event_from_replay_persisted_record(
    record: Mapping[str, Any],
    *,
    source_module: str = "dashboard.runtime.trade_lifecycle_replay_sink",
) -> dict[str, Any]:
    return build_runtime_event(
        record,
        event_type="replay_persisted",
        subsystem="replay",
        severity="INFO",
        source_module=source_module,
        correlation_id=str(record.get("correlation_id") or ""),
        timestamp_utc=str(record.get("persisted_utc") or record.get("timestamp_utc") or ""),
        event_id="",
    )


def runtime_events_from_alert_payload(
    alert_payload: Mapping[str, Any],
    *,
    source_module: str = "dashboard.runtime.alerting_layer",
) -> tuple[dict[str, Any], ...]:
    alerts = alert_payload.get("alerts")
    if not isinstance(alerts, list):
        return ()

    events: list[dict[str, Any]] = []
    for alert in alerts:
        if not isinstance(alert, Mapping):
            continue
        events.append(
            build_runtime_event(
                alert,
                event_type=str(alert.get("alert_id") or "alert_event"),
                subsystem="alerting",
                severity=str(alert.get("severity") or "INFO"),
                source_module=str(alert.get("source") or source_module),
                timestamp_utc=str(alert.get("generated_utc") or ""),
            )
        )
    return tuple(events)


def runtime_event_from_ws_message(
    message: Mapping[str, Any],
    *,
    source_module: str = "dashboard.runtime.ws_bridge",
) -> dict[str, Any]:
    return build_runtime_event(
        message,
        event_type=str(message.get("message_type") or "websocket_message"),
        subsystem=str(message.get("section") or "websocket"),
        severity="INFO",
        source_module=source_module,
        timestamp_utc=str(message.get("generated_at") or ""),
    )


def runtime_event_to_ws_message(
    event: RuntimeEvent | Mapping[str, Any],
    *,
    sequence: int,
    stale_after_ms: int = 15000,
) -> dict[str, Any]:
    normalized = normalize_runtime_event(event)
    section = str(normalized.get("subsystem") or "runtime")
    return {
        "message_type": str(normalized.get("event_type") or "runtime_event"),
        "payload_version": str(normalized.get("schema_version") or RUNTIME_EVENT_SCHEMA_VERSION),
        "generated_at": str(normalized.get("timestamp_utc") or ""),
        "sequence": int(sequence),
        "stale_after_ms": int(stale_after_ms),
        "changed_sections": [section],
        "section": section,
        "transport": "runtime_event_bus",
        "data": {section: normalized.get("payload", {})},
        "event": normalized,
    }


def publish_shadow_runtime_event(
    event_publisher: Callable[[dict[str, Any]], Any] | None,
    event: RuntimeEvent | Mapping[str, Any],
    *,
    strict: bool = False,
    logger: Callable[[str], None] | None = None,
) -> bool:
    if event_publisher is None:
        return False

    try:
        event_publisher(normalize_runtime_event(event))
        return True
    except Exception as exc:
        if logger is not None:
            logger(f"[EVENT BUS WARN] shadow publish failed: {str(exc)[:80]}")
        if strict:
            raise
        return False


def safe_json_dumps(value: Any) -> str:
    return json.dumps(_json_safe(value), sort_keys=True, separators=(",", ":"), default=str)


_DEFAULT_RUNTIME_EVENT_BUS = RuntimeEventBus(max_recent=5000)


def get_default_runtime_event_bus() -> RuntimeEventBus:
    return _DEFAULT_RUNTIME_EVENT_BUS


def _parse_subscription_filter(subsystem: str, event_type: str) -> tuple[str, str]:
    subsystem_text = str(subsystem or "").strip()
    event_type_text = str(event_type or "").strip()
    if not event_type_text and "/" in subsystem_text:
        subsystem_text, event_type_text = subsystem_text.split("/", 1)
    return _normalize_filter(subsystem_text), _normalize_filter(event_type_text)


def _normalize_filter(value: Any) -> str:
    return str(value or "").strip().lower()


def _normalize_severity(value: Any) -> str:
    severity = str(value or "INFO").strip().upper()
    return severity if severity in _SEVERITIES else "INFO"


def _event_id(payload: Mapping[str, Any], *, prefix: str = "EVT") -> str:
    serialized = safe_json_dumps(payload)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:20].upper()
    return f"{prefix}-{digest}"


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        safe: dict[str, Any] = {}
        for key, item in value.items():
            safe_key = str(key)
            safe[safe_key] = "REDACTED" if _is_sensitive_key(safe_key) else _json_safe(item)
        return safe
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
    "RUNTIME_EVENT_BUS_VERSION",
    "RUNTIME_EVENT_REDACTION_STATUS",
    "RUNTIME_EVENT_SCHEMA_VERSION",
    "RuntimeEvent",
    "RuntimeEventBus",
    "RuntimeEventHandler",
    "RuntimeEventSubscription",
    "build_runtime_event",
    "get_default_runtime_event_bus",
    "is_runtime_event",
    "normalize_runtime_event",
    "publish_shadow_runtime_event",
    "runtime_event_from_replay_payload",
    "runtime_event_from_replay_persisted_record",
    "runtime_event_from_ws_message",
    "runtime_event_to_replay_envelope",
    "runtime_event_to_ws_message",
    "runtime_events_from_alert_payload",
    "safe_json_dumps",
]
