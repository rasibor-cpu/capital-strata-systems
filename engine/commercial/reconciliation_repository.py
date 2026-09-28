"""Durable persistence for commercial reconciliation exceptions.

SQLite-backed, append/update-safe storage for reconciliation exception history.
This repository stores evidence metadata only; it has no provider credentials,
collection initiation, charging, broker execution, or money-movement capability.
"""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from engine.commercial.reconciliation_service import ReconciliationException


class ReconciliationRepository:
    def __init__(self, db_path: str):
        self.db_path = str(Path(db_path))
        self._init_schema()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS commercial_reconciliation_exceptions (
                    exception_id TEXT PRIMARY KEY,
                    exception_key TEXT NOT NULL UNIQUE,
                    collection_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    expected TEXT NOT NULL,
                    observed TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    resolved_at TEXT,
                    resolution_reference TEXT,
                    resolved_by TEXT
                )"""
            )
            conn.execute(
                """CREATE INDEX IF NOT EXISTS idx_commercial_recon_collection
                   ON commercial_reconciliation_exceptions(collection_id)"""
            )

    def save(self, item: ReconciliationException, *, exception_key: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO commercial_reconciliation_exceptions
                   (exception_id, exception_key, collection_id, reason, expected, observed,
                    created_at, resolved_at, resolution_reference, resolved_by)
                   VALUES (?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(exception_key) DO UPDATE SET
                     resolved_at=excluded.resolved_at,
                     resolution_reference=excluded.resolution_reference,
                     resolved_by=excluded.resolved_by""",
                (
                    item.exception_id, exception_key, item.collection_id, item.reason,
                    item.expected, item.observed, item.created_at.isoformat(),
                    self._dt(item.resolved_at), item.resolution_reference, item.resolved_by,
                ),
            )

    def get_by_exception_id(self, exception_id: str) -> Optional[ReconciliationException]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM commercial_reconciliation_exceptions WHERE exception_id=?",
                (exception_id,),
            ).fetchone()
        return self._hydrate(row) if row else None

    def get_by_key(self, exception_key: str) -> Optional[ReconciliationException]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM commercial_reconciliation_exceptions WHERE exception_key=?",
                (exception_key,),
            ).fetchone()
        return self._hydrate(row) if row else None

    def list_all(self) -> List[ReconciliationException]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM commercial_reconciliation_exceptions ORDER BY created_at, exception_id"
            ).fetchall()
        return [self._hydrate(row) for row in rows]

    def list_open(self) -> List[ReconciliationException]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM commercial_reconciliation_exceptions
                   WHERE resolved_at IS NULL ORDER BY created_at, exception_id"""
            ).fetchall()
        return [self._hydrate(row) for row in rows]

    @staticmethod
    def _dt(value):
        return value.isoformat() if value else None

    @staticmethod
    def _parse_dt(value):
        return datetime.fromisoformat(value) if value else None

    def _hydrate(self, row) -> ReconciliationException:
        return ReconciliationException(
            collection_id=row["collection_id"],
            reason=row["reason"],
            expected=row["expected"],
            observed=row["observed"],
            exception_id=row["exception_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            resolved_at=self._parse_dt(row["resolved_at"]),
            resolution_reference=row["resolution_reference"],
            resolved_by=row["resolved_by"],
        )
