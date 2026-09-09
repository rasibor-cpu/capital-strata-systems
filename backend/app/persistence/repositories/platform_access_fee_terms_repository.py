from __future__ import annotations

import json
from typing import Any

from backend.app.persistence.repositories.base_repository import (
    BaseRepository,
)
from backend.commercialization.platform_access_fee_terms import (
    CommercialPlatformAccessFeeTerms,
)


class PlatformAccessFeeTermsRepository(BaseRepository):
    """
    Persistence boundary for immutable COM-002U platform access fee terms.

    Deliberately exposes no update or delete method.

    Duplicate insertion for the same access_terms_id fails at the database
    primary-key constraint rather than rewriting commercial terms.
    """

    def create_terms(
        self,
        terms: CommercialPlatformAccessFeeTerms,
    ) -> None:
        if not isinstance(terms, CommercialPlatformAccessFeeTerms):
            raise TypeError("terms must be CommercialPlatformAccessFeeTerms")
        self.execute(
            """
            INSERT INTO platform_access_fee_terms (
                access_terms_id,
                billing_currency,
                access_fee_amount,
                billing_frequency,
                effective_from,
                effective_to,
                evidence_refs_json,
                accepted
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                terms.access_terms_id,
                terms.billing_currency,
                str(terms.access_fee_amount),
                terms.billing_frequency.value,
                terms.effective_from,
                terms.effective_to,
                json.dumps(
                    list(terms.evidence_refs),
                    separators=(",", ":"),
                ),
                1 if terms.accepted else 0,
            ),
        )

    def get_by_access_terms_id(
        self,
        access_terms_id: str,
    ) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT *
            FROM platform_access_fee_terms
            WHERE access_terms_id = ?
            """,
            (access_terms_id,),
        )

        if row is None:
            return None

        return dict(row)

    def list_all(
        self,
    ) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT *
            FROM platform_access_fee_terms
            ORDER BY created_at ASC, access_terms_id ASC
            """
        )

        return [dict(row) for row in rows]
