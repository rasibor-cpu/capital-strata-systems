from __future__ import annotations

import json
from typing import Any

from backend.app.persistence.repositories.base_repository import (
    BaseRepository,
)
from backend.commercialization.invoice_candidate import (
    CommercialInvoiceCandidate,
)


class InvoiceCandidateRepository(BaseRepository):
    """
    Persistence boundary for immutable COM-002J commercial
    invoice candidates.

    Deliberately exposes no update or delete method.

    One authoritative invoice candidate exists per billable commercial
    period. Duplicate insertion for the same policy_id + period_start +
    period_end fails at the composite primary-key constraint rather
    than rewriting candidate history.
    """

    def create_candidate(
        self,
        candidate: CommercialInvoiceCandidate,
    ) -> None:
        self.execute(
            """
            INSERT INTO commercial_invoice_candidates (
                policy_id,
                terms_id,
                billing_profile_id,
                currency,
                period_start,
                period_end,
                candidate_amount,
                assessed_at,
                status,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candidate.policy_id,
                candidate.terms_id,
                candidate.billing_profile_id,
                candidate.currency,
                candidate.period_start,
                candidate.period_end,
                str(candidate.candidate_amount),
                candidate.assessed_at,
                candidate.status.value,
                json.dumps(
                    list(candidate.evidence_refs),
                    separators=(",", ":"),
                ),
            ),
        )

    def get_by_period(
        self,
        policy_id: str,
        period_start: str,
        period_end: str,
    ) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT *
            FROM commercial_invoice_candidates
            WHERE policy_id = ?
              AND period_start = ?
              AND period_end = ?
            """,
            (policy_id, period_start, period_end),
        )

        if row is None:
            return None

        return dict(row)

    def get_by_policy_id(
        self,
        policy_id: str,
    ) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT *
            FROM commercial_invoice_candidates
            WHERE policy_id = ?
            ORDER BY period_start ASC, period_end ASC,
                     created_at ASC
            """,
            (policy_id,),
        )

        return [dict(row) for row in rows]

    def get_by_terms_id(
        self,
        terms_id: str,
    ) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT *
            FROM commercial_invoice_candidates
            WHERE terms_id = ?
            ORDER BY policy_id ASC, period_start ASC,
                     period_end ASC, created_at ASC
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
            FROM commercial_invoice_candidates
            WHERE billing_profile_id = ?
            ORDER BY policy_id ASC, period_start ASC,
                     period_end ASC, created_at ASC
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
            FROM commercial_invoice_candidates
            ORDER BY policy_id ASC, period_start ASC,
                     period_end ASC, created_at ASC
            """
        )

        return [dict(row) for row in rows]
