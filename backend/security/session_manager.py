from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class Session:
    session_id: str
    username: str
    role: str
    created: float
    last_activity: float
    idle_timeout_seconds: int
    max_session_seconds: int
    hard_expiry_epoch: float
    is_active: bool = True
    ended: float | None = None
    end_reason: str | None = None


class SessionManager:
    """
    CSS Session Manager (Upgraded)

    - Idle timeout enforcement
    - Max session lifetime enforcement
    - Activity tracking
    """

    def __init__(
        self,
        idle_timeout_seconds: int = 3600,
        max_session_seconds: int = 28800,
    ):
        self.sessions = {}
        self.default_idle_timeout = idle_timeout_seconds
        self.default_max_session = max_session_seconds

    def _now(self) -> float:
        return time.time()

    def create_session(
        self,
        username: str,
        role: str,
        idle_timeout_seconds: Optional[int] = None,
        max_session_seconds: Optional[int] = None,
    ) -> Session:

        now = self._now()

        idle = idle_timeout_seconds or self.default_idle_timeout
        max_s = max_session_seconds or self.default_max_session

        session_id = secrets.token_hex(16)

        session = Session(
            session_id=session_id,
            username=username,
            role=role,
            created=now,
            last_activity=now,
            idle_timeout_seconds=idle,
            max_session_seconds=max_s,
            hard_expiry_epoch=now + max_s,
        )

        self.sessions[session_id] = session
        return session

    def _expiry_decision(self, session: Session):
        now = self._now()

        if not session.is_active:
            return True, session.end_reason or "inactive"

        if now - session.last_activity > session.idle_timeout_seconds:
            return True, "idle_timeout"

        if now > session.hard_expiry_epoch:
            return True, "max_session_lifetime"

        return False, None

    def _mark_expired(self, session: Session, reason: str):
        if session.is_active:
            session.is_active = False
            session.ended = self._now()
            session.end_reason = reason
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        session = self.sessions.get(str(session_id))
        if session is None:
            return None

        expired, reason = self._expiry_decision(session)
        if expired:
            return self._mark_expired(session, reason)

        return session

    def touch_session(self, session_id: str):
        session = self.sessions.get(str(session_id))
        if session is None:
            return None

        expired, reason = self._expiry_decision(session)
        if expired:
            return self._mark_expired(session, reason)

        session.last_activity = self._now()
        return session

    def get_session_status(self, session_id: str):
        session = self.sessions.get(str(session_id))
        if session is None:
            return {"active": False}

        expired, reason = self._expiry_decision(session)
        if expired:
            self._mark_expired(session, reason)

        return {
            "active": session.is_active,
            "created": session.created,
            "last_activity": session.last_activity,
            "idle_timeout_seconds": session.idle_timeout_seconds,
            "max_session_seconds": session.max_session_seconds,
            "end_reason": session.end_reason,
        }

    def destroy_session(self, session_id: str, reason: str = "destroyed"):
        session = self.sessions.get(str(session_id))
        if session:
            self._mark_expired(session, reason)
            del self.sessions[str(session_id)]