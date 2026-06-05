"""Durable repository for Phase 1 legal acceptance records.

The repository is append-only and implements the LegalAcceptanceStore protocol
used by LegalAcceptanceService. It is deliberately isolated from broker,
execution, dashboard, analytics, and PnL code.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from backend.app.compliance.legal_acceptance import LegalAcceptanceRecord
from backend.app.compliance.legal_acceptance_versions import REQUIRED_ACCEPTANCE_TYPES
from backend.app.persistence.repositories.base_repository import BaseRepository


class LegalAcceptanceRepository(BaseRepository):
    """SQLite-backed durable acceptance repository.

    The table is append-only from the service perspective: new acceptance events
    are inserted and historical rows are not updated. Latest-record retrieval is
    version-aware and ordered by the persisted acceptance timestamp.
    """

    def __init__(self, *, ensure_schema: bool = True) -> None:
        if ensure_schema:
            self.ensure_schema()

    def ensure_schema(self) -> None:
        """Create the acceptance table and lookup indexes when absent."""

        self.execute(
            """
            CREATE TABLE IF NOT EXISTS legal_acceptances (
                acceptance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                acceptance_type TEXT NOT NULL,
                acceptance_version TEXT NOT NULL,
                accepted INTEGER NOT NULL CHECK (accepted IN (0, 1)),
                accepted_at TEXT NOT NULL,
                audit_reference TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )

        self.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_legal_acceptances_user_type_time
            ON legal_acceptances (
                user_id,
                acceptance_type,
                accepted_at DESC,
                acceptance_id DESC
            )
            """
        )

        self.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_legal_acceptances_user_type_version_time
            ON legal_acceptances (
                user_id,
                acceptance_type,
                acceptance_version,
                accepted_at DESC,
                acceptance_id DESC
            )
            """
        )

    def save(self, record: LegalAcceptanceRecord) -> LegalAcceptanceRecord:
        """Persist an acceptance record and return the saved record."""

        self.execute(
            """
            INSERT INTO legal_acceptances (
                user_id,
                acceptance_type,
                acceptance_version,
                accepted,
                accepted_at,
                audit_reference
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                record.user_id,
                record.acceptance_type,
                record.acceptance_version,
                1 if record.accepted else 0,
                record.accepted_at.isoformat(),
                record.audit_reference,
            ),
        )

        return record

    def load_acceptance(
        self,
        *,
        user_id: str,
        acceptance_type: str,
        acceptance_version: str,
    ) -> LegalAcceptanceRecord | None:
        """Load the latest record for a user, type, and exact version."""

        row = self.fetch_one(
            """
            SELECT
                user_id,
                acceptance_type,
                acceptance_version,
                accepted,
                accepted_at,
                audit_reference
            FROM legal_acceptances
            WHERE user_id = ?
              AND acceptance_type = ?
              AND acceptance_version = ?
            ORDER BY accepted_at DESC, acceptance_id DESC
            LIMIT 1
            """,
            (user_id, acceptance_type, acceptance_version),
        )

        if row is None:
            return None

        return self._row_to_record(row)

    def latest_for(
        self,
        user_id: str,
        acceptance_type: str,
    ) -> LegalAcceptanceRecord | None:
        """Return the latest persisted acceptance record for a user and type."""

        row = self.fetch_one(
            """
            SELECT
                user_id,
                acceptance_type,
                acceptance_version,
                accepted,
                accepted_at,
                audit_reference
            FROM legal_acceptances
            WHERE user_id = ?
              AND acceptance_type = ?
            ORDER BY accepted_at DESC, acceptance_id DESC
            LIMIT 1
            """,
            (user_id, acceptance_type),
        )

        if row is None:
            return None

        return self._row_to_record(row)

    def latest_for_version(
        self,
        *,
        user_id: str,
        acceptance_type: str,
        acceptance_version: str,
    ) -> LegalAcceptanceRecord | None:
        """Return the latest persisted acceptance for an exact version."""

        return self.load_acceptance(
            user_id=user_id,
            acceptance_type=acceptance_type,
            acceptance_version=acceptance_version,
        )

    def all_for_user(self, user_id: str) -> tuple[LegalAcceptanceRecord, ...]:
        """Return all persisted acceptance records for a user."""

        rows = self.fetch_all(
            """
            SELECT
                user_id,
                acceptance_type,
                acceptance_version,
                accepted,
                accepted_at,
                audit_reference
            FROM legal_acceptances
            WHERE user_id = ?
            ORDER BY accepted_at DESC, acceptance_id DESC
            """,
            (user_id,),
        )

        return tuple(self._row_to_record(row) for row in rows)

    def all_required_for_user(
        self,
        user_id: str,
        acceptance_types: Iterable[str] = REQUIRED_ACCEPTANCE_TYPES,
    ) -> dict[str, LegalAcceptanceRecord | None]:
        """Return latest records for all required acceptance types."""

        return {
            acceptance_type: self.latest_for(user_id, acceptance_type)
            for acceptance_type in acceptance_types
        }

    def _row_to_record(self, row: Any) -> LegalAcceptanceRecord:
        """Convert a SQLite row to a validated LegalAcceptanceRecord."""

        return LegalAcceptanceRecord.from_mapping(
            {
                "user_id": row["user_id"],
                "acceptance_type": row["acceptance_type"],
                "acceptance_version": row["acceptance_version"],
                "accepted": bool(row["accepted"]),
                "accepted_at": row["accepted_at"],
                "audit_reference": row["audit_reference"],
            }
        )