from __future__ import annotations

import json
from typing import Any

from backend.app.persistence.repositories.base_repository import (
    BaseRepository,
)
from backend.commercialization.receivable_reversal import (
    CommercialReceivableReversalRecord,
)


class ReceivableReversalRepository(BaseRepository):
    """
    Persistence boundary for immutable COM-002O commercial
    receivable full-reversal records.

    Deliberately exposes no update or delete method.

    One full reversal exists per recognized receivable. Duplicate
    insertion for the same receivable_id fails at the uniqueness
    constraint rather than rewriting reversal history. Callers must
    supply an already validated CommercialReceivableReversalRecord;
    this repository does not build reversals from raw ids.
    """

    def create_reversal(
        self,
        record: CommercialReceivableReversalRecord,
    ) -> None:
        self.execute(
            """
            INSERT INTO commercial_receivable_reversals (
                reversal_id,
                receivable_id,
                invoice_id,
                correction_id,
                currency,
                reversal_amount,
                reversed_at,
                reason_reference,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.reversal_id,
                record.receivable_id,
                record.invoice_id,
                record.correction_id,
                record.currency,
                str(record.reversal_amount),
                record.reversed_at,
                record.reason_reference,
                json.dumps(
                    list(record.evidence_refs),
                    separators=(",", ":"),
                ),
            ),
        )

    def get_by_reversal_id(
        self,
        reversal_id: str,
    ) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT *
            FROM commercial_receivable_reversals
            WHERE reversal_id = ?
            """,
            (reversal_id,),
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
            FROM commercial_receivable_reversals
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
            FROM commercial_receivable_reversals
            WHERE invoice_id = ?
            ORDER BY reversed_at ASC, reversal_id ASC,
                     created_at ASC
            """,
            (invoice_id,),
        )

        return [dict(row) for row in rows]

    def get_by_correction_id(
        self,
        correction_id: str,
    ) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT *
            FROM commercial_receivable_reversals
            WHERE correction_id = ?
            ORDER BY reversed_at ASC, reversal_id ASC,
                     created_at ASC
            """,
            (correction_id,),
        )

        return [dict(row) for row in rows]

    def list_all(
        self,
    ) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT *
            FROM commercial_receivable_reversals
            ORDER BY reversed_at ASC, reversal_id ASC,
                     created_at ASC
            """
        )

        return [dict(row) for row in rows]
