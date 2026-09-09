from __future__ import annotations

import json
from typing import Any

from backend.app.persistence.repositories.base_repository import (
    BaseRepository,
)
from backend.commercialization.receivable_credit import (
    CommercialReceivableCreditRecord,
)


class ReceivableCreditRepository(BaseRepository):
    """
    Persistence boundary for immutable COM-002S commercial
    receivable credit records.

    Deliberately exposes no update or delete method.

    Multiple credits per receivable and invoice are permitted.
    Callers must supply an already validated
    CommercialReceivableCreditRecord; this repository does not build
    credits from raw ids or enforce aggregate caps.
    """

    def create_credit(
        self,
        record: CommercialReceivableCreditRecord,
    ) -> None:
        self.execute(
            """
            INSERT INTO commercial_receivable_credits (
                credit_id,
                receivable_id,
                invoice_id,
                currency,
                credit_amount,
                credited_at,
                reason_reference,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.credit_id,
                record.receivable_id,
                record.invoice_id,
                record.currency,
                str(record.credit_amount),
                record.credited_at,
                record.reason_reference,
                json.dumps(
                    list(record.evidence_refs),
                    separators=(",", ":"),
                ),
            ),
        )

    def get_by_credit_id(
        self,
        credit_id: str,
    ) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT *
            FROM commercial_receivable_credits
            WHERE credit_id = ?
            """,
            (credit_id,),
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
            FROM commercial_receivable_credits
            WHERE receivable_id = ?
            ORDER BY credited_at ASC, credit_id ASC,
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
            FROM commercial_receivable_credits
            WHERE invoice_id = ?
            ORDER BY credited_at ASC, credit_id ASC,
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
            FROM commercial_receivable_credits
            ORDER BY credited_at ASC, credit_id ASC,
                     created_at ASC
            """
        )

        return [dict(row) for row in rows]
