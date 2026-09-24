"""Durable, fail-closed collection persistence.

SQLite-backed repository for collection lifecycle state and idempotency recovery.
No provider credentials or live debit capability are stored here.
"""
import json
import sqlite3
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

from engine.domain.collections import CollectionStatus, CollectionTransaction


class CollectionRepository:
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
                """CREATE TABLE IF NOT EXISTS commercial_collections (
                    collection_id TEXT PRIMARY KEY,
                    obligation_id TEXT NOT NULL,
                    customer_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    amount TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    provider_reference TEXT,
                    settlement_reference TEXT,
                    initiated_at TEXT,
                    settled_at TEXT,
                    reconciled_at TEXT,
                    ledger_txn_id TEXT,
                    meta_json TEXT NOT NULL
                )"""
            )

    def save(self, c: CollectionTransaction) -> None:
        payload = (
            c.collection_id, c.obligation_id, c.customer_id, c.account_id,
            str(c.amount), c.currency, c.idempotency_key, c.status.value,
            c.provider_reference, c.settlement_reference,
            self._dt(c.initiated_at), self._dt(c.settled_at),
            self._dt(c.reconciled_at), c.ledger_txn_id,
            json.dumps(c.meta, sort_keys=True, default=str),
        )
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO commercial_collections VALUES
                (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(collection_id) DO UPDATE SET
                  status=excluded.status,
                  provider_reference=excluded.provider_reference,
                  settlement_reference=excluded.settlement_reference,
                  initiated_at=excluded.initiated_at,
                  settled_at=excluded.settled_at,
                  reconciled_at=excluded.reconciled_at,
                  ledger_txn_id=excluded.ledger_txn_id,
                  meta_json=excluded.meta_json""",
                payload,
            )

    def get_by_idempotency_key(self, key: str) -> Optional[CollectionTransaction]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM commercial_collections WHERE idempotency_key=?", (key,)
            ).fetchone()
        return self._hydrate(row) if row else None

    @staticmethod
    def _dt(value):
        return value.isoformat() if value else None

    @staticmethod
    def _parse_dt(value):
        return datetime.fromisoformat(value) if value else None

    def _hydrate(self, row) -> CollectionTransaction:
        return CollectionTransaction(
            collection_id=row["collection_id"],
            obligation_id=row["obligation_id"],
            customer_id=row["customer_id"],
            account_id=row["account_id"],
            amount=Decimal(row["amount"]),
            currency=row["currency"],
            idempotency_key=row["idempotency_key"],
            status=CollectionStatus(row["status"]),
            provider_reference=row["provider_reference"],
            settlement_reference=row["settlement_reference"],
            initiated_at=self._parse_dt(row["initiated_at"]),
            settled_at=self._parse_dt(row["settled_at"]),
            reconciled_at=self._parse_dt(row["reconciled_at"]),
            ledger_txn_id=row["ledger_txn_id"],
            meta=json.loads(row["meta_json"] or "{}"),
        )
