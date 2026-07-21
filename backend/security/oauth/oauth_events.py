"""Immutable OAuth governance event stream."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import threading
import uuid
from typing import Any

from backend.security.oauth.oauth_models import utc_now
from backend.security.vault_redaction import redact_text


@dataclass(frozen=True)
class OAuthEvent:
    event_id: str
    timestamp: str
    oauth_id: str
    provider: str
    action: str
    result: str
    reason: str
    correlation_id: str
    authorization_performed: bool = False
    refresh_performed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class OAuthEventStream:
    def __init__(self):
        self._events: list[OAuthEvent] = []
        self._lock = threading.RLock()

    def publish(
        self,
        *,
        oauth_id: str,
        provider: str,
        action: str,
        result: str,
        reason: str,
        correlation_id: str,
    ) -> OAuthEvent:
        event = OAuthEvent(
            event_id=str(uuid.uuid4()),
            timestamp=utc_now(),
            oauth_id=str(oauth_id),
            provider=str(provider).upper(),
            action=str(action).upper(),
            result=str(result).upper(),
            reason=redact_text(str(reason)).upper()[:512],
            correlation_id=str(correlation_id),
        )
        with self._lock:
            self._events.append(event)
        return event

    def snapshot(self) -> tuple[OAuthEvent, ...]:
        with self._lock:
            return tuple(self._events)


__all__ = ["OAuthEvent", "OAuthEventStream"]
