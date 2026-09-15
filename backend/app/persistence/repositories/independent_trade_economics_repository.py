from __future__ import annotations

import json
from typing import Any

from backend.app.persistence.repositories.base_repository import BaseRepository
from backend.commercialization.independent_trade_economics import (
    IndependentTradeEconomics,
)


class IndependentTradeEconomicsRepository(BaseRepository):
    """Append-only persistence for independent/customer-controlled economics."""

    def create_record(self, record: IndependentTradeEconomics) -> None:
        self.execute(
            """
            INSERT INTO independent_trade_economics (
                trade_id,
                account_reference,
                calculation_timestamp,
                attribution_class,
                realized_pnl,
                currency,
                platform_charge_rate,
                platform_charge_amount,
                charge_basis,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.trade_id,
                record.account_reference,
                record.calculation_timestamp,
                record.attribution_class.value,
                str(record.realized_pnl),
                record.currency,
                str(record.platform_charge_rate),
                str(record.platform_charge_amount),
                record.charge_basis.value,
                json.dumps(list(record.evidence_refs), separators=(",", ":")),
            ),
        )

    def get_by_trade_id(self, trade_id: str) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT * FROM independent_trade_economics
            WHERE trade_id = ?
            """,
            (trade_id,),
        )
        return dict(row) if row is not None else None

    def list_for_account_period(
        self,
        *,
        account_reference: str,
        period_start: str,
        period_end: str,
    ) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT *
            FROM independent_trade_economics
            WHERE account_reference = ?
              AND calculation_timestamp >= ?
              AND calculation_timestamp < ?
            ORDER BY calculation_timestamp ASC, trade_id ASC
            """,
            (account_reference, period_start, period_end),
        )
        return [dict(row) for row in rows]
