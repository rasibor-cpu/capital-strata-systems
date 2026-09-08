from __future__ import annotations

import json
from typing import Any

from backend.app.persistence.repositories.base_repository import BaseRepository
from backend.commercialization.trade_provenance import TradeProvenance


class TradeProvenanceRepository(BaseRepository):
    """
    Persistence boundary for immutable COM-002A trade provenance.

    Deliberately exposes no update or delete method.

    A trade may receive one authoritative provenance record. Attempting
    to insert another record for the same trade_id fails at the database
    primary-key constraint rather than rewriting historical attribution.
    """

    def create_provenance(
        self,
        provenance: TradeProvenance,
    ) -> None:
        self.execute(
            """
            INSERT INTO trade_provenance (
                trade_id,
                advice_id,
                attribution_class,
                mandate_compliance,
                recommendation_timestamp,
                acceptance_timestamp,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                provenance.trade_id,
                provenance.advice_id,
                provenance.attribution_class.value,
                provenance.mandate_compliance.value,
                provenance.recommendation_timestamp,
                provenance.acceptance_timestamp,
                json.dumps(
                    list(provenance.evidence_refs),
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
            FROM trade_provenance
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
            FROM trade_provenance
            WHERE advice_id = ?
            ORDER BY created_at ASC, trade_id ASC
            """,
            (advice_id,),
        )

        return [dict(row) for row in rows]