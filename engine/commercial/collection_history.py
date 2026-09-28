"""Append-only lifecycle history for commercial collections.

``CollectionRepository`` keeps the current state of a collection; this
repository keeps every state it passed through, so a refund, reversal or
chargeback adds history instead of hiding the original settlement. Each
(collection, state) is recorded exactly once, which makes recording
replay-safe, and SQLite triggers abort any UPDATE or DELETE.

Evidence metadata only: no provider credentials or money-movement capability.
"""
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

RECONCILED = "RECONCILED"


@dataclass(frozen=True)
class CollectionEvent:
    seq: int
    collection_id: str
    from_status: str
    to_status: str
    occurred_at: str
    provider_reference: Optional[str] = None
    settlement_reference: Optional[str] = None
    ledger_txn_id: Optional[str] = None
    reconciliation_reference: Optional[str] = None
    actor_id: Optional[str] = None
    reason: Optional[str] = None


class CollectionHistoryRepository:
    def __init__(self, db_path: str):
        self.db_path = str(Path(db_path))
        conn = self._connect()
        try:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS commercial_collection_events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    collection_id TEXT NOT NULL,
                    from_status TEXT NOT NULL,
                    to_status TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    provider_reference TEXT,
                    settlement_reference TEXT,
                    ledger_txn_id TEXT,
                    reconciliation_reference TEXT,
                    actor_id TEXT,
                    reason TEXT,
                    UNIQUE(collection_id, to_status)
                )"""
            )
            for op in ("UPDATE", "DELETE"):
                conn.execute(
                    f"""CREATE TRIGGER IF NOT EXISTS commercial_collection_events_no_{op.lower()}
                    BEFORE {op} ON commercial_collection_events
                    BEGIN SELECT RAISE(ABORT, 'commercial collection history is append-only'); END"""
                )
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        return conn

    def record(
        self,
        collection_id: str,
        *,
        from_status: str,
        to_status: str,
        occurred_at: Optional[datetime] = None,
        provider_reference: Optional[str] = None,
        settlement_reference: Optional[str] = None,
        ledger_txn_id: Optional[str] = None,
        reconciliation_reference: Optional[str] = None,
        actor_id: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> bool:
        """Record reaching ``to_status``. Returns False if it was already recorded."""
        when = (occurred_at or datetime.now(timezone.utc)).isoformat()
        conn = self._connect()
        try:
            cur = conn.execute(
                """INSERT OR IGNORE INTO commercial_collection_events
                (collection_id, from_status, to_status, occurred_at, provider_reference,
                 settlement_reference, ledger_txn_id, reconciliation_reference, actor_id, reason)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (collection_id, from_status, to_status, when, provider_reference, settlement_reference,
                 ledger_txn_id, reconciliation_reference, actor_id, reason),
            )
            return cur.rowcount == 1
        finally:
            conn.close()

    def history(self, collection_id: str) -> List[CollectionEvent]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM commercial_collection_events WHERE collection_id=? ORDER BY seq", (collection_id,)
            ).fetchall()
        finally:
            conn.close()
        return [CollectionEvent(**dict(r)) for r in rows]
