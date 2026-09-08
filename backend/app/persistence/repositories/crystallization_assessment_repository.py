from __future__ import annotations

import json
from typing import Any

from backend.app.persistence.repositories.base_repository import (
    BaseRepository,
)
from backend.commercialization.performance_crystallization import (
    CrystallizationAssessment,
)


class CrystallizationAssessmentRepository(BaseRepository):
    """
    Persistence boundary for immutable COM-002E crystallization
    assessments.

    Deliberately exposes no update or delete method.

    One authoritative assessment exists per policy commercial period.
    Duplicate insertion for the same policy_id + period_start +
    period_end fails at the composite primary-key constraint rather
    than rewriting crystallization history.
    """

    def create_assessment(
        self,
        assessment: CrystallizationAssessment,
    ) -> None:
        self.execute(
            """
            INSERT INTO crystallization_assessments (
                policy_id,
                terms_id,
                currency,
                period_start,
                period_end,
                assessed_at,
                shadow_entitlement_total,
                crystallizable_amount,
                status,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                assessment.policy_id,
                assessment.terms_id,
                assessment.currency,
                assessment.period_start,
                assessment.period_end,
                assessment.assessed_at,
                str(assessment.shadow_entitlement_total),
                str(assessment.crystallizable_amount),
                assessment.status.value,
                json.dumps(
                    list(assessment.evidence_refs),
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
            FROM crystallization_assessments
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
            FROM crystallization_assessments
            WHERE policy_id = ?
            ORDER BY period_start ASC, period_end ASC,
                     created_at ASC
            """,
            (policy_id,),
        )

        return [dict(row) for row in rows]

    def list_all(
        self,
    ) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT *
            FROM crystallization_assessments
            ORDER BY policy_id ASC, period_start ASC,
                     period_end ASC, created_at ASC
            """
        )

        return [dict(row) for row in rows]
