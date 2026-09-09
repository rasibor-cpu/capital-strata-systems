from __future__ import annotations

import json
from typing import Any

from backend.app.persistence.repositories.base_repository import (
    BaseRepository,
)
from backend.commercialization.receivable_due import (
    CommercialReceivableDueRecord,
)


class ReceivableDueRepository(BaseRepository):
    """
    Persistence boundary for immutable COM-002P commercial
    receivable due-date records.

    Deliberately exposes no update or delete method.

    One due-date record exists per recognized receivable. Duplicate
    insertion for the same receivable_id fails at the uniqueness
    constraint rather than rewriting due-date history. Callers must
    supply an already validated CommercialReceivableDueRecord; this
    repository does not build due dates from raw ids.
    """

    def create_due_record(
        self,
        record: CommercialReceivableDueRecord,
    ) -> None:
        self.execute(
            """
            INSERT INTO commercial_receivable_due_records (
                due_record_id,
                receivable_id,
                invoice_id,
                due_date,
                determined_at,
                terms_reference,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.due_record_id,
                record.receivable_id,
                record.invoice_id,
                record.due_date,
                record.determined_at,
                record.terms_reference,
                json.dumps(
                    list(record.evidence_refs),
                    separators=(",", ":"),
                ),
            ),
        )

    def get_by_due_record_id(
        self,
        due_record_id: str,
    ) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT *
            FROM commercial_receivable_due_records
            WHERE due_record_id = ?
            """,
            (due_record_id,),
        )

        if row is None:
            return None

        return dict(row)

    def get_by_receivable_id(
        self,
        receivable_id: str,
    ) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT *
            FROM commercial_receivable_due_records
            WHERE receivable_id = ?
            """,
            (receivable_id,),
        )

        if row is None:
            return None

        return dict(row)

    def get_by_invoice_id(
        self,
        invoice_id: str,
    ) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT *
            FROM commercial_receivable_due_records
            WHERE invoice_id = ?
            ORDER BY determined_at ASC, due_record_id ASC,
                     created_at ASC
            """,
            (invoice_id,),
        )

        return [dict(row) for row in rows]

    def list_all(
        self,
    ) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT *
            FROM commercial_receivable_due_records
            ORDER BY determined_at ASC, due_record_id ASC,
                     created_at ASC
            """
        )

        return [dict(row) for row in rows]
