from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from backend.app.persistence.repositories.base_repository import (
    BaseRepository,
)
from backend.commercialization.billable_obligation import (
    CommercialBillableObligation,
)


class BillableObligationRepository(BaseRepository):
    """
    Persistence boundary for immutable COM-002G commercial
    billable-obligation decisions.

    Deliberately exposes no update or delete method.

    One authoritative billable obligation exists per crystallized
    commercial period. Duplicate insertion for the same policy_id +
    period_start + period_end fails at the composite primary-key
    constraint rather than rewriting billable history.
    """

    def create_obligation(
        self,
        obligation: CommercialBillableObligation,
    ) -> None:
        readiness = self.fetch_one(
            "SELECT * FROM commercial_settlement_readiness "
            "WHERE policy_id = ? AND period_start = ? AND period_end = ?",
            (obligation.policy_id, obligation.period_start, obligation.period_end),
        )
        if readiness is not None and "final_fee_selection_id" in readiness.keys() and readiness["final_fee_selection_id"] is not None:
            for name in ("terms_id", "currency"):
                if getattr(obligation, name) != readiness[name]:
                    raise ValueError(f"billable {name} mismatches final-fee readiness")
            if obligation.billable_amount != Decimal(readiness["economic_amount"]):
                raise ValueError("billable amount mismatches final-fee readiness")
            if obligation.status.value == "BILLABLE" and readiness["status"] != "READY":
                raise ValueError("BILLABLE requires READY final-fee readiness")
        self.execute(
            """
            INSERT INTO commercial_billable_obligations (
                policy_id,
                terms_id,
                currency,
                period_start,
                period_end,
                billable_amount,
                recognized_at,
                status,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                obligation.policy_id,
                obligation.terms_id,
                obligation.currency,
                obligation.period_start,
                obligation.period_end,
                str(obligation.billable_amount),
                obligation.recognized_at,
                obligation.status.value,
                json.dumps(
                    list(obligation.evidence_refs),
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
            FROM commercial_billable_obligations
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
            FROM commercial_billable_obligations
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
            FROM commercial_billable_obligations
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
            FROM commercial_billable_obligations
            ORDER BY policy_id ASC, period_start ASC,
                     period_end ASC, created_at ASC
            """
        )

        return [dict(row) for row in rows]
