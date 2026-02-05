"""
In-memory token store (Phase 1)

- Opaque tokens issued on successful login
- TTL enforcement
- Fail-closed validation
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, List
import secrets


UTC = timezone.utc


@dataclass(frozen=True)
class SessionInfo:
    token: str
    username: str
    roles: List[str]
    issued_at_utc: datetime
    expires_at_utc: datetime


class TokenStore:
    def __init__(self) -> None:
        self._sessions: Dict[str, SessionInfo] = {}

    def issue(self, username: str, roles: List[str], ttl_minutes: int) -> SessionInfo:
        now = datetime.now(UTC)
        token = secrets.token_urlsafe(32)
        expires = now + timedelta(minutes=max(1, int(ttl_minutes)))
        info = SessionInfo(
            token=token,
            username=username,
            roles=list(roles),
            issued_at_utc=now,
            expires_at_utc=expires,
        )
        self._sessions[token] = info
        return info

    def revoke(self, token: str) -> bool:
        if not token:
            return False
        return self._sessions.pop(token, None) is not None

    def validate(self, token: str) -> Optional[SessionInfo]:
        if not token or not isinstance(token, str):
            return None

        info = self._sessions.get(token)
        if info is None:
            return None

        now = datetime.now(UTC)
        if now >= info.expires_at_utc:
            # expire & fail closed
            self._sessions.pop(token, None)
            return None

        return info


# Singleton store (Phase 1). Later replace with Redis/DB.
token_store = TokenStore()
