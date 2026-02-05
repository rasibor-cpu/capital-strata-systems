from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, List
import random

UTC = timezone.utc


@dataclass(frozen=True)
class SessionInfo:
    token: str
    username: str
    roles: List[str]
    issued_at_utc: datetime
    expires_at_utc: datetime


@dataclass(frozen=True)
class ChallengeInfo:
    code: str  # 6 digits
    username: str
    roles: List[str]
    issued_at_utc: datetime
    expires_at_utc: datetime


class TokenStore:
    def __init__(self) -> None:
        self._sessions: Dict[str, SessionInfo] = {}
        self._challenges: Dict[str, ChallengeInfo] = {}

    def _generate_6d(self) -> str:
        return f"{random.randint(0, 999999):06d}"

    # -------------------------
    # Challenge (login step 1)
    # -------------------------
    def issue_challenge(self, username: str, roles: List[str], ttl_minutes: int) -> ChallengeInfo:
        now = datetime.now(UTC)
        code = self._generate_6d()
        expires = now + timedelta(minutes=max(1, int(ttl_minutes)))

        info = ChallengeInfo(
            code=code,
            username=username,
            roles=list(roles),
            issued_at_utc=now,
            expires_at_utc=expires,
        )
        self._challenges[code] = info
        return info

    def consume_challenge(self, code: str) -> Optional[ChallengeInfo]:
        if not code or (not code.isdigit()) or len(code) != 6:
            return None

        info = self._challenges.get(code)
        if info is None:
            return None

        if datetime.now(UTC) >= info.expires_at_utc:
            self._challenges.pop(code, None)
            return None

        # one-time use
        self._challenges.pop(code, None)
        return info

    # -------------------------
    # Session (login step 2)
    # -------------------------
    def issue_session(self, username: str, roles: List[str], ttl_minutes: int) -> SessionInfo:
        now = datetime.now(UTC)
        token = self._generate_6d()
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
        return self._sessions.pop(token, None) is not None

    def validate_session(self, token: str) -> Optional[SessionInfo]:
        if not token or (not token.isdigit()) or len(token) != 6:
            return None

        info = self._sessions.get(token)
        if info is None:
            return None

        if datetime.now(UTC) >= info.expires_at_utc:
            self._sessions.pop(token, None)
            return None

        return info


token_store = TokenStore()
