from __future__ import annotations

import json
from typing import Any

from backend.app.persistence.repositories.base_repository import (
    BaseRepository,
)
from backend.commercialization.performance_compensation import (
    PerformanceCompensationTerms,
)


class PerformanceCompensationTermsRepository(BaseRepository):
    """
    Persistence boundary for immutable COM-002D compensation terms.

    Deliberately exposes no update or delete method.

    Duplicate insertion for the same terms_id fails at the database
    primary-key constraint rather than rewriting commercial terms.
    """

    def create_terms(
        self,
        terms: PerformanceCompensationTerms,
    ) -> None:
        self.execute(
            """
            INSERT INTO performance_compensation_terms (
                terms_id,
                currency,
                performance_compensation_rate,
                effective_from,
                effective_to,
                evidence_refs_json,
                accepted
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                terms.terms_id,
                terms.currency,
                str(terms.performance_compensation_rate),
                terms.effective_from,
                terms.effective_to,
                json.dumps(
                    list(terms.evidence_refs),
                    separators=(",", ":"),
                ),
                1 if terms.accepted else 0,
            ),
        )

    def get_by_terms_id(
        self,
        terms_id: str,
    ) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT *
            FROM performance_compensation_terms
            WHERE terms_id = ?
            """,
            (terms_id,),
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
            FROM performance_compensation_terms
            ORDER BY created_at ASC, terms_id ASC
            """
        )

        return [dict(row) for row in rows]
