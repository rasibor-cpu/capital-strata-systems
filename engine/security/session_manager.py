"""
Session Manager (v1)
-------------------
Controls user login/logout and session lifecycle.

Rules:
- Every action must be tied to a session_id
- Sessions are immutable once created
- Logout always writes an audit event
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict
import uuid

from engine.security.audit_log import AuditLogger, AuditEventType


def _utc_now_compat() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass(frozen=True)
class Session:
    session_id: str
    user_id: str
    started_at: datetime
    expires_at: datetime
    business_date: str
    active: bool = True


class SessionManager:
    def __init__(
        self,
        *,
        audit: AuditLogger,
        session_ttl_minutes: int = 120,
    ):
        self.audit = audit
        self.session_ttl = timedelta(minutes=session_ttl_minutes)
        self._sessions: Dict[str, Session] = {}

    def login(self, *, user_id: str, business_date: str) -> Session:
        now = _utc_now_compat()
        session = Session(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            started_at=now,
            expires_at=now + self.session_ttl,
            business_date=business_date,
            active=True,
        )

        self._sessions[session.session_id] = session

        self.audit.log(
            event_type=AuditEventType.ACTION,
            user_id=user_id,
            role=None,
            session_id=session.session_id,
            screen="AUTH",
            action="LOGIN",
            resource="SESSION",
            success=True,
            meta={"business_date": business_date},
        )

        return session

    def logout(self, *, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if not session:
            return

        self.audit.log(
            event_type=AuditEventType.ACTION,
            user_id=session.user_id,
            role=None,
            session_id=session_id,
            screen="AUTH",
            action="LOGOUT",
            resource="SESSION",
            success=True,
        )

        del self._sessions[session_id]

    def require_active(self, session_id: str) -> Session:
        session = self._sessions.get(session_id)
        if not session:
            raise PermissionError("Invalid or expired session")

        if _utc_now_compat() > session.expires_at:
            self.logout(session_id=session_id)
            raise PermissionError("Session expired")

        return session
