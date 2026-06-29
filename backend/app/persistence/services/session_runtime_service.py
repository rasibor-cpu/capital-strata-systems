from datetime import datetime, timezone
from uuid import uuid4

from backend.app.persistence.services.persistence_service import (
    PersistenceService,
)


class SessionRuntimeService:
    """
    Runtime session lifecycle persistence manager.

    Responsibilities:
    - create runtime sessions
    - update session states
    - close sessions cleanly
    - provide active session tracking

    IMPORTANT:
    - no governance logic
    - no orchestration logic
    - no broker execution logic
    """

    def __init__(self) -> None:
        self.persistence = PersistenceService()

    def create_runtime_session(
        self,
        mode: str,
        broker_name: str,
        broker_mode: str,
    ) -> str:

        session_id = str(uuid4())

        started_at = (
            datetime.now(timezone.utc).isoformat()
        )

        self.persistence.sessions.create_session(
            session_id=session_id,
            status="active",
            mode=mode,
            broker_name=broker_name,
            broker_mode=broker_mode,
            started_at=started_at,
        )

        return session_id

    def pause_session(
        self,
        session_id: str,
        reason: str | None = None,
    ) -> None:

        self.persistence.sessions.update_session_status(
            session_id=session_id,
            previous_state="active",
            new_state="paused",
            reason=reason,
        )

    def resume_session(
        self,
        session_id: str,
        reason: str | None = None,
    ) -> None:

        self.persistence.sessions.update_session_status(
            session_id=session_id,
            previous_state="paused",
            new_state="active",
            reason=reason,
        )

    def close_session(
        self,
        session_id: str,
    ) -> None:

        ended_at = (
            datetime.now(timezone.utc).isoformat()
        )

        self.persistence.sessions.close_session(
            session_id=session_id,
            ended_at=ended_at,
        )

    def get_active_sessions(self):
        return (
            self.persistence.sessions
            .get_active_sessions()
        )