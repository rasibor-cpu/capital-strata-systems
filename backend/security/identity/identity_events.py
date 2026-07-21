"""Immutable in-process event stream for identity and secret governance."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import threading
import uuid
from typing import Any

from backend.security.identity.identity_models import utc_now


@dataclass(frozen=True)
class IdentityEvent:
    event_id: str
    timestamp: str
    event_type: str
    identity_id: str
    resource_id: str
    correlation_id: str
    result: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class IdentityEventStream:
    def __init__(self):
        self._events: list[IdentityEvent] = []
        self._lock = threading.RLock()

    def publish(
        self,
        *,
        event_type: str,
        identity_id: str,
        resource_id: str,
        result: str,
        correlation_id: str | None = None,
    ) -> IdentityEvent:
        event = IdentityEvent(
            event_id=str(uuid.uuid4()),
            timestamp=utc_now(),
            event_type=str(event_type).upper(),
            identity_id=str(identity_id),
            resource_id=str(resource_id),
            correlation_id=str(correlation_id or uuid.uuid4()),
            result=str(result).upper(),
        )
        with self._lock:
            self._events.append(event)
        return event

    def snapshot(self) -> tuple[IdentityEvent, ...]:
        with self._lock:
            return tuple(self._events)


__all__ = ["IdentityEvent", "IdentityEventStream"]
