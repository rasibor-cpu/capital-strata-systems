from __future__ import annotations

from decimal import Decimal
from typing import Any

from backend.app.persistence.repositories.base_repository import (
    BaseRepository,
)


class TradeRepository(BaseRepository):
    """
    Repository for durable trade persistence and recovery.
    """

    def create_trade(
        self,
        trade_id: str,
        session_id: str,
        broker_name: str,
        broker_mode: str,
        symbol: str,
        direction: str,
        status: str,
        order_type: str,
        quantity: Decimal,
        filled_quantity: Decimal,
        entry_price: Decimal,
        opened_at: str,
        raw_payload_json: str | None = None,
    ) -> None:
        self.execute(
            """
            INSERT INTO trades (
                trade_id,
                session_id,
                broker_name,
                broker_mode,
                symbol,
                direction,
                status,
                order_type,
                quantity,
                filled_quantity,
                entry_price,
                opened_at,
                raw_payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade_id,
                session_id,
                broker_name,
                broker_mode,
                symbol,
                direction,
                status,
                order_type,
                str(quantity),
                str(filled_quantity),
                str(entry_price),
                opened_at,
                raw_payload_json,
            ),
        )

    def update_trade_status(
        self,
        trade_id: str,
        status: str,
    ) -> None:
        self.execute(
            """
            UPDATE trades
            SET
                status = ?,
                updated_at = datetime('now')
            WHERE trade_id = ?
            """,
            (
                status,
                trade_id,
            ),
        )

    def close_trade(
        self,
        trade_id: str,
        exit_price: Decimal,
        realized_pnl: Decimal,
        closed_at: str,
    ) -> None:
        self.execute(
            """
            UPDATE trades
            SET
                status = 'closed',
                exit_price = ?,
                realized_pnl = ?,
                closed_at = ?,
                updated_at = datetime('now')
            WHERE trade_id = ?
            """,
            (
                str(exit_price),
                str(realized_pnl),
                closed_at,
                trade_id,
            ),
        )

    def get_trade(
        self,
        trade_id: str,
    ) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT *
            FROM trades
            WHERE trade_id = ?
            """,
            (trade_id,),
        )

        if row is None:
            return None

        return dict(row)

    def get_open_trades(
        self,
        session_id: str,
    ) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT *
            FROM trades
            WHERE
                session_id = ?
                AND status IN (
                    'pending',
                    'open',
                    'partially_filled'
                )
            ORDER BY opened_at ASC
            """,
            (session_id,),
        )

        return [dict(row) for row in rows]

    def trade_exists(
        self,
        session_id: str,
        symbol: str,
        direction: str,
    ) -> bool:
        row = self.fetch_one(
            """
            SELECT trade_id
            FROM trades
            WHERE
                session_id = ?
                AND symbol = ?
                AND direction = ?
                AND status IN (
                    'pending',
                    'open',
                    'partially_filled'
                )
            LIMIT 1
            """,
            (
                session_id,
                symbol,
                direction,
            ),
        )

        return row is not None