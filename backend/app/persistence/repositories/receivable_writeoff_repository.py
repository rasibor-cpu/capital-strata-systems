from __future__ import annotations

import json
from typing import Any

from backend.app.persistence.repositories.base_repository import (
    BaseRepository,
)
from backend.commercialization.receivable_writeoff import (
    CommercialReceivableWriteOffRecord,
)


class ReceivableWriteOffRepository(BaseRepository):
    """
    Persistence boundary for immutable COM-002S commercial
    receivable write-off records.

    Deliberately exposes no update or delete method.

    Multiple write-offs per receivable and invoice are permitted.
    Callers must supply an already validated
    CommercialReceivableWriteOffRecord; this repository does not build
    write-offs from raw ids or post bad-debt GL.
    """

    def create_writeoff(
        self,
        record: CommercialReceivableWriteOffRecord,
    ) -> None:
        self.execute(
            """
            INSERT INTO commercial_receivable_writeoffs (
                writeoff_id,
                receivable_id,
                invoice_id,
                currency,
                writeoff_amount,
                written_off_at,
                reason_reference,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.writeoff_id,
                record.receivable_id,
                record.invoice_id,
                record.currency,
                str(record.writeoff_amount),
                record.written_off_at,
                record.reason_reference,
                json.dumps(
                    list(record.evidence_refs),
                    separators=(",", ":"),
                ),
            ),
        )

    def get_by_writeoff_id(
        self,
        writeoff_id: str,
    ) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT *
            FROM commercial_receivable_writeoffs
            WHERE writeoff_id = ?
            """,
            (writeoff_id,),
        )

        if row is None:
            return None

        return dict(row)

    def get_by_receivable_id(
        self,
        receivable_id: str,
    ) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT *
            FROM commercial_receivable_writeoffs
            WHERE receivable_id = ?
            ORDER BY written_off_at ASC, writeoff_id ASC,
                     created_at ASC
            """,
            (receivable_id,),
        )

        return [dict(row) for row in rows]

    def get_by_invoice_id(
        self,
        invoice_id: str,
    ) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT *
            FROM commercial_receivable_writeoffs
            WHERE invoice_id = ?
            ORDER BY written_off_at ASC, writeoff_id ASC,
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
            FROM commercial_receivable_writeoffs
            ORDER BY written_off_at ASC, writeoff_id ASC,
                     created_at ASC
            """
        )

        return [dict(row) for row in rows]
