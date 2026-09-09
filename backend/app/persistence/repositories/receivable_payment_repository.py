from __future__ import annotations

import json
from typing import Any

from backend.app.persistence.repositories.base_repository import (
    BaseRepository,
)
from backend.commercialization.receivable_payment import (
    CommercialReceivablePaymentRecord,
)


class ReceivablePaymentRepository(BaseRepository):
    """
    Persistence boundary for immutable COM-002Q commercial
    payment observation records.

    Deliberately exposes no update or delete method.

    Payment identity is independent of any receivable. Callers must
    supply an already validated CommercialReceivablePaymentRecord;
    this repository does not build payments from raw ids.
    """

    def create_payment(
        self,
        record: CommercialReceivablePaymentRecord,
    ) -> None:
        self.execute(
            """
            INSERT INTO commercial_receivable_payments (
                payment_id,
                currency,
                payment_amount,
                observed_at,
                external_reference,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                record.payment_id,
                record.currency,
                str(record.payment_amount),
                record.observed_at,
                record.external_reference,
                json.dumps(
                    list(record.evidence_refs),
                    separators=(",", ":"),
                ),
            ),
        )

    def get_by_payment_id(
        self,
        payment_id: str,
    ) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT *
            FROM commercial_receivable_payments
            WHERE payment_id = ?
            """,
            (payment_id,),
        )

        if row is None:
            return None

        return dict(row)

    def get_by_external_reference(
        self,
        external_reference: str,
    ) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT *
            FROM commercial_receivable_payments
            WHERE external_reference = ?
            ORDER BY observed_at ASC, payment_id ASC,
                     created_at ASC
            """,
            (external_reference,),
        )

        return [dict(row) for row in rows]

    def list_all(
        self,
    ) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT *
            FROM commercial_receivable_payments
            ORDER BY observed_at ASC, payment_id ASC,
                     created_at ASC
            """
        )

        return [dict(row) for row in rows]
