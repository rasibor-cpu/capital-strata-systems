from __future__ import annotations

import json
from typing import Any

from backend.app.persistence.repositories.base_repository import (
    BaseRepository,
)
from backend.commercialization.performance_crystallization import (
    PerformanceCompensationLifecyclePolicy,
)


class PerformanceCompensationLifecyclePolicyRepository(BaseRepository):
    """
    Persistence boundary for immutable COM-002E lifecycle policies.

    Deliberately exposes no update or delete method.

    Duplicate insertion for the same policy_id fails at the database
    primary-key constraint rather than rewriting commercial policy.
    """

    def create_policy(
        self,
        policy: PerformanceCompensationLifecyclePolicy,
    ) -> None:
        self.execute(
            """
            INSERT INTO performance_compensation_lifecycle_policies (
                policy_id,
                terms_id,
                currency,
                crystallization_frequency,
                effective_from,
                evidence_refs_json,
                crystallize_on_termination,
                effective_to
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                policy.policy_id,
                policy.terms_id,
                policy.currency,
                policy.crystallization_frequency.value,
                policy.effective_from,
                json.dumps(
                    list(policy.evidence_refs),
                    separators=(",", ":"),
                ),
                1 if policy.crystallize_on_termination else 0,
                policy.effective_to,
            ),
        )

    def get_by_policy_id(
        self,
        policy_id: str,
    ) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT *
            FROM performance_compensation_lifecycle_policies
            WHERE policy_id = ?
            """,
            (policy_id,),
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
            FROM performance_compensation_lifecycle_policies
            WHERE terms_id = ?
            ORDER BY created_at ASC, policy_id ASC
            """,
            (terms_id,),
        )

        return [dict(row) for row in rows]

    def list_all(
        self,
    ) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT *
            FROM performance_compensation_lifecycle_policies
            ORDER BY created_at ASC, policy_id ASC
            """
        )

        return [dict(row) for row in rows]
