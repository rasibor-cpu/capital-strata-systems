from __future__ import annotations

import json
from typing import Any

from backend.app.persistence.repositories.base_repository import (
    BaseRepository,
)
from backend.commercialization.settlement_readiness import (
    CommercialSettlementReadiness,
)


class SettlementReadinessRepository(BaseRepository):
    """
    Persistence boundary for immutable COM-002F commercial
    settlement-readiness decisions.

    Deliberately exposes no update or delete method.

    One authoritative readiness decision exists per crystallized
    commercial period. Duplicate insertion for the same policy_id +
    period_start + period_end fails at the composite primary-key
    constraint rather than rewriting readiness history.
    """

    def create_readiness(
        self,
        readiness: CommercialSettlementReadiness,
    ) -> None:
        self.execute(
            """
            INSERT INTO commercial_settlement_readiness (
                policy_id,
                terms_id,
                currency,
                period_start,
                period_end,
                crystallizable_amount,
                assessed_at,
                status,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                readiness.policy_id,
                readiness.terms_id,
                readiness.currency,
                readiness.period_start,
                readiness.period_end,
                str(readiness.crystallizable_amount),
                readiness.assessed_at,
                readiness.status.value,
                json.dumps(
                    list(readiness.evidence_refs),
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
            FROM commercial_settlement_readiness
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
            FROM commercial_settlement_readiness
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
            FROM commercial_settlement_readiness
            WHERE terms_id = ?
            ORDER BY policy_id ASC, period_start ASC,
                     period_end ASC, created_at ASC
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
            FROM commercial_settlement_readiness
            ORDER BY policy_id ASC, period_start ASC,
                     period_end ASC, created_at ASC
            """
        )

        return [dict(row) for row in rows]
