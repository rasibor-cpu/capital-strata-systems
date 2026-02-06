"""
Token + OTP store (in-memory) — REA Capital Trading Engine

- OTP: 6-digit codes per username, time-limited.
- Session token: opaque UUID per validated session.
- Safe defaults: missing/expired => invalid.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import secrets
import uuid
from typing import Dict, Optional, Any, List

from .auth_config import OTP_TTL_SECONDS


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class SessionInfo:
    username: str
    roles: List[str]
    issued_at_utc: datetime
    expires_at_utc: datetime

    def to_public_dict(self) -> Dict[str, Any]:
        return {
            "username": self.username,
            "roles": self.roles,
            "issued_at_utc": self.issued_at_utc.isoformat(),
            "expires_at_utc": self.expires_at_utc.isoformat(),
        }


@dataclass
class _OtpRecord:
    code: str
    expires_at_utc: datetime


class TokenStore:
    def __init__(self) -> None:
        self._sessions: Dict[str, SessionInfo] = {}
        self._otp: Dict[str, _OtpRecord] = {}

    # -------------------------
    # OTP
    # -------------------------
    def generate_otp(self, username: str) -> str:
        """
        Generate a 6-digit OTP and store it for username.
        """
        username = (username or "").strip().lower()
        if not username:
            raise ValueError("username is required")

        # 6-digit numeric; preserve leading zeros
        code = f"{secrets.randbelow(1_000_000):06d}"
        expires = _utcnow() + timedelta(seconds=int(OTP_TTL_SECONDS))
        self._otp[username] = _OtpRecord(code=code, expires_at_utc=expires)
        return code

    def verify_otp(self, username: str, code: str) -> bool:
        username = (username or "").strip().lower()
        code = (code or "").strip()

        rec = self._otp.get(username)
        if rec is None:
            return False

        # Expired?
        if _utcnow() >= rec.expires_at_utc:
            # burn it
            self._otp.pop(username, None)
            return False

        ok = secrets.compare_digest(rec.code, code)
        if ok:
            # OTP is one-time; burn it
            self._otp.pop(username, None)
        return ok

    def otp_expires_in_seconds(self, username: str) -> Optional[int]:
        username = (username or "").strip().lower()
        rec = self._otp.get(username)
        if rec is None:
            return None
        remain = int((rec.expires_at_utc - _utcnow()).total_seconds())
        return max(0, remain)

    # -------------------------
    # Session tokens
    # -------------------------
    def create_session(self, username: str, roles: List[str], minutes: int = 60) -> str:
        username = (username or "").strip().lower()
        if not username:
            raise ValueError("username is required")

        issued = _utcnow()
        expires = issued + timedelta(minutes=int(minutes))
        token = str(uuid.uuid4())
        self._sessions[token] = SessionInfo(
            username=username,
            roles=list(roles or []),
            issued_at_utc=issued,
            expires_at_utc=expires,
        )
        return token

    def validate(self, token: str) -> Optional[SessionInfo]:
        token = (token or "").strip()
        if not token:
            return None
        info = self._sessions.get(token)
        if info is None:
            return None
        if _utcnow() >= info.expires_at_utc:
            self._sessions.pop(token, None)
            return None
        return info

    def revoke(self, token: str) -> bool:
        token = (token or "").strip()
        return self._sessions.pop(token, None) is not None


token_store = TokenStore()
