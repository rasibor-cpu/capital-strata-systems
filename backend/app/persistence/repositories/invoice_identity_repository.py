from __future__ import annotations

import json
from typing import Any

from backend.app.persistence.repositories.base_repository import (
    BaseRepository,
)
from backend.commercialization.invoice_identity import (
    CommercialInvoiceIdentityAllocation,
)


class InvoiceIdentityRepository(BaseRepository):
    """
    Persistence boundary for immutable COM-002K commercial
    invoice identity allocations.

    Deliberately exposes no update or delete method.

    One allocation exists per invoice candidate period. Duplicate
    insertion for the same policy_id + period_start + period_end fails
    at the uniqueness constraint rather than rewriting identity
    history. Non-null invoice_number values are also unique; NULL
    invoice_number values may coexist under SQLite NULL semantics.
    """

    def create_allocation(
        self,
        allocation: CommercialInvoiceIdentityAllocation,
    ) -> None:
        self.execute(
            """
            INSERT INTO commercial_invoice_identity_allocations (
                invoice_id,
                policy_id,
                terms_id,
                billing_profile_id,
                currency,
                period_start,
                period_end,
                invoice_amount,
                allocated_at,
                evidence_refs_json,
                invoice_number
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                allocation.invoice_id,
                allocation.policy_id,
                allocation.terms_id,
                allocation.billing_profile_id,
                allocation.currency,
                allocation.period_start,
                allocation.period_end,
                str(allocation.invoice_amount),
                allocation.allocated_at,
                json.dumps(
                    list(allocation.evidence_refs),
                    separators=(",", ":"),
                ),
                allocation.invoice_number,
            ),
        )

    def get_by_invoice_id(
        self,
        invoice_id: str,
    ) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT *
            FROM commercial_invoice_identity_allocations
            WHERE invoice_id = ?
            """,
            (invoice_id,),
        )

        if row is None:
            return None

        return dict(row)

    def get_by_candidate_period(
        self,
        policy_id: str,
        period_start: str,
        period_end: str,
    ) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT *
            FROM commercial_invoice_identity_allocations
            WHERE policy_id = ?
              AND period_start = ?
              AND period_end = ?
            """,
            (policy_id, period_start, period_end),
        )

        if row is None:
            return None

        return dict(row)

    def get_by_invoice_number(
        self,
        invoice_number: str,
    ) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT *
            FROM commercial_invoice_identity_allocations
            WHERE invoice_number = ?
            """,
            (invoice_number,),
        )

        if row is None:
            return None

        return dict(row)

    def get_by_terms_id(
        self,
        terms_id: str,
    ) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT *
            FROM commercial_invoice_identity_allocations
            WHERE terms_id = ?
            ORDER BY policy_id ASC, period_start ASC,
                     period_end ASC, invoice_id ASC,
                     created_at ASC
            """,
            (terms_id,),
        )

        return [dict(row) for row in rows]

    def get_by_billing_profile_id(
        self,
        billing_profile_id: str,
    ) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT *
            FROM commercial_invoice_identity_allocations
            WHERE billing_profile_id = ?
            ORDER BY policy_id ASC, period_start ASC,
                     period_end ASC, invoice_id ASC,
                     created_at ASC
            """,
            (billing_profile_id,),
        )

        return [dict(row) for row in rows]

    def list_all(
        self,
    ) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT *
            FROM commercial_invoice_identity_allocations
            ORDER BY policy_id ASC, period_start ASC,
                     period_end ASC, invoice_id ASC,
                     created_at ASC
            """
        )

        return [dict(row) for row in rows]
