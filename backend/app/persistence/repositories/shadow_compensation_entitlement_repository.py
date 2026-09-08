from __future__ import annotations

import json
from typing import Any

from backend.app.persistence.repositories.base_repository import (
    BaseRepository,
)
from backend.commercialization.performance_compensation import (
    ShadowCompensationEntitlement,
)


class ShadowCompensationEntitlementRepository(BaseRepository):
    """
    Persistence boundary for immutable COM-002D shadow entitlements.

    Deliberately exposes no update or delete method.

    Each COM-002C accounting transition may produce one authoritative
    shadow entitlement. Duplicate insertion for the same trade_id fails
    at the database primary-key constraint rather than rewriting
    entitlement history.

    Insertion requires existing compensation terms and an existing
    performance-accounting transition.
    """

    def create_entitlement(
        self,
        entitlement: ShadowCompensationEntitlement,
    ) -> None:
        self.execute(
            """
            INSERT INTO shadow_compensation_entitlements (
                trade_id,
                terms_id,
                currency,
                new_economic_gain,
                compensation_rate,
                shadow_compensation_amount,
                calculation_timestamp,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entitlement.trade_id,
                entitlement.terms_id,
                entitlement.currency,
                str(entitlement.new_economic_gain),
                str(entitlement.compensation_rate),
                str(entitlement.shadow_compensation_amount),
                entitlement.calculation_timestamp,
                json.dumps(
                    list(entitlement.evidence_refs),
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
            FROM shadow_compensation_entitlements
            WHERE trade_id = ?
            """,
            (trade_id,),
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
            FROM shadow_compensation_entitlements
            WHERE terms_id = ?
            ORDER BY created_at ASC, trade_id ASC
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
            FROM shadow_compensation_entitlements
            ORDER BY created_at ASC, trade_id ASC
            """
        )

        return [dict(row) for row in rows]
