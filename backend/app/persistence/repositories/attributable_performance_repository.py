from __future__ import annotations

import json
from typing import Any

from backend.app.persistence.repositories.base_repository import (
    BaseRepository,
)
from backend.commercialization.performance_attribution import (
    AttributablePerformance,
)


class AttributablePerformanceRepository(BaseRepository):
    """
    Persistence boundary for immutable COM-002B attributable performance.

    Deliberately exposes no update or delete method.

    A trade may receive one authoritative attributable-performance record.
    Duplicate insertion for the same trade_id fails at the database
    primary-key constraint rather than rewriting performance history.
    """

    def create_attributable_performance(
        self,
        performance: AttributablePerformance,
    ) -> None:
        self.execute(
            """
            INSERT INTO attributable_performance (
                trade_id,
                advice_id,
                realized_pnl,
                currency,
                verification_timestamp,
                provenance_evidence_refs_json,
                economics_evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                performance.trade_id,
                performance.advice_id,
                str(performance.realized_pnl),
                performance.currency,
                performance.verification_timestamp,
                json.dumps(
                    list(performance.provenance_evidence_refs),
                    separators=(",", ":"),
                ),
                json.dumps(
                    list(performance.economics_evidence_refs),
                    separators=(",", ":"),
                ),
            ),
        )

    def get_by_trade_id(
        self,
        trade_id: str,
    ) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT *
            FROM attributable_performance
            WHERE trade_id = ?
            """,
            (trade_id,),
        )

        if row is None:
            return None

        return dict(row)

    def get_by_advice_id(
        self,
        advice_id: str,
    ) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT *
            FROM attributable_performance
            WHERE advice_id = ?
            ORDER BY created_at ASC, trade_id ASC
            """,
            (advice_id,),
        )

        return [dict(row) for row in rows]
