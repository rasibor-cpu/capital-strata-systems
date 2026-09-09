from __future__ import annotations

import json
from typing import Any

from backend.app.persistence.repositories.base_repository import (
    BaseRepository,
)
from backend.commercialization.invoice_correction import (
    CommercialInvoiceCorrectionRecord,
)


class InvoiceCorrectionRepository(BaseRepository):
    """
    Persistence boundary for immutable COM-002M commercial
    invoice correction events.

    Deliberately exposes no update or delete method.

    Multiple append-only correction events may exist per issued invoice.
    Duplicate insertion for the same correction_id fails at the primary
    key rather than rewriting correction history.
    """

    def create_correction(
        self,
        correction: CommercialInvoiceCorrectionRecord,
    ) -> None:
        self.execute(
            """
            INSERT INTO commercial_invoice_corrections (
                correction_id,
                invoice_id,
                correction_type,
                corrected_at,
                reason_reference,
                evidence_refs_json,
                replacement_invoice_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                correction.correction_id,
                correction.invoice_id,
                correction.correction_type.value,
                correction.corrected_at,
                correction.reason_reference,
                json.dumps(
                    list(correction.evidence_refs),
                    separators=(",", ":"),
                ),
                correction.replacement_invoice_id,
            ),
        )

    def get_by_correction_id(
        self,
        correction_id: str,
    ) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT *
            FROM commercial_invoice_corrections
            WHERE correction_id = ?
            """,
            (correction_id,),
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
            FROM commercial_invoice_corrections
            WHERE invoice_id = ?
            ORDER BY corrected_at ASC, correction_id ASC,
                     created_at ASC
            """,
            (invoice_id,),
        )

        return [dict(row) for row in rows]

    def get_by_replacement_invoice_id(
        self,
        replacement_invoice_id: str,
    ) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT *
            FROM commercial_invoice_corrections
            WHERE replacement_invoice_id = ?
            ORDER BY corrected_at ASC, correction_id ASC,
                     created_at ASC
            """,
            (replacement_invoice_id,),
        )

        return [dict(row) for row in rows]

    def list_all(
        self,
    ) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT *
            FROM commercial_invoice_corrections
            ORDER BY corrected_at ASC, correction_id ASC,
                     created_at ASC
            """
        )

        return [dict(row) for row in rows]
