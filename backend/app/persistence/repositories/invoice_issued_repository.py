from __future__ import annotations

import json
from typing import Any

from backend.app.persistence.repositories.base_repository import (
    BaseRepository,
)
from backend.commercialization.invoice_issued import (
    CommercialInvoiceIssuedRecord,
)


class InvoiceIssuedRepository(BaseRepository):
    """
    Persistence boundary for immutable COM-002L commercial
    invoice issued records.

    Deliberately exposes no update or delete method.

    One issued record exists per allocated invoice identity. Duplicate
    insertion for the same invoice_id fails at the primary-key
    constraint rather than rewriting issuance history.
    """

    def create_issued_record(
        self,
        record: CommercialInvoiceIssuedRecord,
    ) -> None:
        self.execute(
            """
            INSERT INTO commercial_invoice_issued_records (
                invoice_id,
                policy_id,
                terms_id,
                billing_profile_id,
                currency,
                period_start,
                period_end,
                invoice_amount,
                invoice_number,
                issued_at,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.invoice_id,
                record.policy_id,
                record.terms_id,
                record.billing_profile_id,
                record.currency,
                record.period_start,
                record.period_end,
                str(record.invoice_amount),
                record.invoice_number,
                record.issued_at,
                json.dumps(
                    list(record.evidence_refs),
                    separators=(",", ":"),
                ),
            ),
        )

    def get_by_invoice_id(
        self,
        invoice_id: str,
    ) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT *
            FROM commercial_invoice_issued_records
            WHERE invoice_id = ?
            """,
            (invoice_id,),
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
            FROM commercial_invoice_issued_records
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
            FROM commercial_invoice_issued_records
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
            FROM commercial_invoice_issued_records
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
            FROM commercial_invoice_issued_records
            ORDER BY policy_id ASC, period_start ASC,
                     period_end ASC, invoice_id ASC,
                     created_at ASC
            """
        )

        return [dict(row) for row in rows]
