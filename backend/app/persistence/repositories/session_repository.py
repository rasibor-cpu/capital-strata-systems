from __future__ import annotations

from typing import Any

from backend.app.persistence.repositories.base_repository import (
    BaseRepository,
)


class SessionRepository(BaseRepository):
    """
    Repository for durable CSS session persistence.
    """

    def create_session(
        self,
        session_id: str,
        status: str,
        mode: str,
        broker_name: str,
        broker_mode: str,
        started_at: str,
    ) -> None:
        self.execute(
            """
            INSERT INTO sessions (
                session_id,
                started_at,
                status,
                mode,
                broker_name,
                broker_mode
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                started_at,
                status,
                mode,
                broker_name,
                broker_mode,
            ),
        )

    def update_session_status(
        self,
        session_id: str,
        previous_state: str | None,
        new_state: str,
        reason: str | None = None,
    ) -> None:
        with self.transaction():
            self.execute(
                """
                UPDATE sessions
                SET status = ?
                WHERE session_id = ?
                """,
                (
                    new_state,
                    session_id,
                ),
            )

            self.execute(
                """
                INSERT INTO session_state_history (
                    session_id,
                    previous_state,
                    new_state,
                    reason
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    session_id,
                    previous_state,
                    new_state,
                    reason,
                ),
            )

    def close_session(
        self,
        session_id: str,
        ended_at: str,
    ) -> None:
        self.execute(
            """
            UPDATE sessions
            SET
                status = 'closed',
                ended_at = ?
            WHERE session_id = ?
            """,
            (
                ended_at,
                session_id,
            ),
        )

    def get_session(
        self,
        session_id: str,
    ) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT *
            FROM sessions
            WHERE session_id = ?
            """,
            (session_id,),
        )

        if row is None:
            return None

        return dict(row)

    def get_active_sessions(self) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT *
            FROM sessions
            WHERE status != 'closed'
            ORDER BY created_at DESC
            """
        )

        return [dict(row) for row in rows]