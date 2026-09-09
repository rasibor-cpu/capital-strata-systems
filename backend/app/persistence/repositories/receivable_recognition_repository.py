from __future__ import annotations

import json
from typing import Any

from backend.app.persistence.repositories.base_repository import (
    BaseRepository,
)
from backend.commercialization.receivable_recognition import (
    CommercialReceivableRecognitionRecord,
)


class ReceivableRecognitionRepository(BaseRepository):
    """
    Persistence boundary for immutable COM-002N commercial
    receivable recognition records.

    Deliberately exposes no update or delete method.

    One recognition exists per issued invoice. Duplicate insertion for
    the same invoice_id fails at the uniqueness constraint rather than
    rewriting recognition history. Callers must supply an already
    validated CommercialReceivableRecognitionRecord; this repository
    does not build recognition from a raw invoice_id.
    """

    def create_recognition(
        self,
        record: CommercialReceivableRecognitionRecord,
    ) -> None:
        self.execute(
            """
            INSERT INTO commercial_receivable_recognitions (
                receivable_id,
                invoice_id,
                billing_profile_id,
                currency,
                receivable_amount,
                recognized_at,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.receivable_id,
                record.invoice_id,
                record.billing_profile_id,
                record.currency,
                str(record.receivable_amount),
                record.recognized_at,
                json.dumps(
                    list(record.evidence_refs),
                    separators=(",", ":"),
                ),
            ),
        )

    def get_by_receivable_id(
        self,
        receivable_id: str,
    ) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT *
            FROM commercial_receivable_recognitions
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
    ) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT *
            FROM commercial_receivable_recognitions
            WHERE invoice_id = ?
            """,
            (invoice_id,),
        )

        if row is None:
            return None

        return dict(row)

    def get_by_billing_profile_id(
        self,
        billing_profile_id: str,
    ) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT *
            FROM commercial_receivable_recognitions
            WHERE billing_profile_id = ?
            ORDER BY recognized_at ASC, receivable_id ASC,
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
            FROM commercial_receivable_recognitions
            ORDER BY recognized_at ASC, receivable_id ASC,
                     created_at ASC
            """
        )

        return [dict(row) for row in rows]
