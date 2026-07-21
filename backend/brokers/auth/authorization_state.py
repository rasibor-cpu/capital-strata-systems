"""Offline OAuth authorization-state and replay-protection primitives."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import secrets
import threading


class AuthorizationStatus(str, Enum):
    CREATED = "CREATED"
    VALIDATED = "VALIDATED"
    CALLBACK_PENDING = "CALLBACK_PENDING"
    CALLBACK_VALIDATED = "CALLBACK_VALIDATED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class AuthorizationState:
    state_id: str
    state_digest: str
    broker: str
    callback_uri: str
    created_at: str
    expires_at: str
    status: AuthorizationStatus
    correlation_id: str
    used: bool = False


class AuthorizationStateStore:
    def __init__(self):
        self._states: dict[str, AuthorizationState] = {}
        self._lock = threading.RLock()

    def issue(
        self,
        *,
        broker: str,
        callback_uri: str,
        correlation_id: str,
        ttl_seconds: int = 600,
    ) -> tuple[str, AuthorizationState]:
        raw = secrets.token_urlsafe(32)
        state_id = secrets.token_hex(12)
        now = datetime.now(timezone.utc)
        state = AuthorizationState(
            state_id=state_id,
            state_digest=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            broker=str(broker).upper(),
            callback_uri=str(callback_uri),
            created_at=now.isoformat(),
            expires_at=(now + timedelta(seconds=max(1, ttl_seconds))).isoformat(),
            status=AuthorizationStatus.CALLBACK_PENDING,
            correlation_id=correlation_id,
        )
        with self._lock:
            self._states[state_id] = state
        return raw, state

    def consume(self, state_id: str, raw_state: str, *, now: datetime | None = None) -> AuthorizationState:
        with self._lock:
            state = self._states.get(str(state_id))
            if state is None:
                raise PermissionError("OAUTH_STATE_UNKNOWN")
            current = now or datetime.now(timezone.utc)
            if state.used:
                raise PermissionError("OAUTH_STATE_REPLAYED")
            if current >= datetime.fromisoformat(state.expires_at):
                self._states[state_id] = AuthorizationState(**{**state.__dict__, "status": AuthorizationStatus.EXPIRED})
                raise PermissionError("OAUTH_STATE_EXPIRED")
            supplied = hashlib.sha256(str(raw_state).encode("utf-8")).hexdigest()
            if not secrets.compare_digest(supplied, state.state_digest):
                raise PermissionError("OAUTH_STATE_MISMATCH")
            validated = AuthorizationState(
                **{
                    **state.__dict__,
                    "status": AuthorizationStatus.CALLBACK_VALIDATED,
                    "used": True,
                }
            )
            self._states[state_id] = validated
            return validated


__all__ = ["AuthorizationState", "AuthorizationStateStore", "AuthorizationStatus"]
