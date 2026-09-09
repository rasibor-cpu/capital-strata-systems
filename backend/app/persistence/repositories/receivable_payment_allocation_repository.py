from __future__ import annotations

import json
from typing import Any

from backend.app.persistence.repositories.base_repository import (
    BaseRepository,
)
from backend.commercialization.receivable_payment_allocation import (
    CommercialReceivablePaymentAllocationRecord,
)


class ReceivablePaymentAllocationRepository(BaseRepository):
    """
    Persistence boundary for immutable COM-002Q commercial
    receivable payment-allocation records.

    Deliberately exposes no update or delete method.

    Multiple allocations per payment and per receivable are permitted.
    Callers must supply an already validated
    CommercialReceivablePaymentAllocationRecord; this repository does
    not allocate from raw ids or aggregate open balances.
    """

    def create_allocation(
        self,
        record: CommercialReceivablePaymentAllocationRecord,
    ) -> None:
        self.execute(
            """
            INSERT INTO commercial_receivable_payment_allocations (
                allocation_id,
                payment_id,
                receivable_id,
                invoice_id,
                currency,
                allocated_amount,
                allocated_at,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.allocation_id,
                record.payment_id,
                record.receivable_id,
                record.invoice_id,
                record.currency,
                str(record.allocated_amount),
                record.allocated_at,
                json.dumps(
                    list(record.evidence_refs),
                    separators=(",", ":"),
                ),
            ),
        )

    def get_by_allocation_id(
        self,
        allocation_id: str,
    ) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT *
            FROM commercial_receivable_payment_allocations
            WHERE allocation_id = ?
            """,
            (allocation_id,),
        )

        if row is None:
            return None

        return dict(row)

    def get_by_payment_id(
        self,
        payment_id: str,
    ) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT *
            FROM commercial_receivable_payment_allocations
            WHERE payment_id = ?
            ORDER BY allocated_at ASC, allocation_id ASC,
                     created_at ASC
            """,
            (payment_id,),
        )

        return [dict(row) for row in rows]

    def get_by_receivable_id(
        self,
        receivable_id: str,
    ) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT *
            FROM commercial_receivable_payment_allocations
            WHERE receivable_id = ?
            ORDER BY allocated_at ASC, allocation_id ASC,
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
            FROM commercial_receivable_payment_allocations
            WHERE invoice_id = ?
            ORDER BY allocated_at ASC, allocation_id ASC,
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
            FROM commercial_receivable_payment_allocations
            ORDER BY allocated_at ASC, allocation_id ASC,
                     created_at ASC
            """
        )

        return [dict(row) for row in rows]
