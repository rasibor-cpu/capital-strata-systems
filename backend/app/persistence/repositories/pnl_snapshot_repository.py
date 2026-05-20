from __future__ import annotations

from decimal import Decimal
from typing import Any

from backend.app.persistence.repositories.base_repository import (
    BaseRepository,
)


class PnlSnapshotRepository(BaseRepository):
    """
    Repository for durable PnL and account-state snapshots.
    """

    def create_snapshot(
        self,
        session_id: str,
        account_id: str,
        broker_name: str,
        broker_mode: str,
        realized_pnl: Decimal,
        unrealized_pnl: Decimal,
        equity: Decimal,
        available_cash: Decimal,
        open_positions: int,
        winning_positions: int,
        losing_positions: int,
        snapshot_reason: str | None = None,
    ) -> None:
        self.execute(
            """
            INSERT INTO pnl_snapshots (
                session_id,
                account_id,
                broker_name,
                broker_mode,
                realized_pnl,
                unrealized_pnl,
                equity,
                available_cash,
                open_positions,
                winning_positions,
                losing_positions,
                snapshot_reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                account_id,
                broker_name,
                broker_mode,
                str(realized_pnl),
                str(unrealized_pnl),
                str(equity),
                str(available_cash),
                open_positions,
                winning_positions,
                losing_positions,
                snapshot_reason,
            ),
        )

    def get_latest_snapshot(
        self,
        session_id: str,
    ) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT *
            FROM pnl_snapshots
            WHERE session_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (session_id,),
        )

        if row is None:
            return None

        return dict(row)

    def get_snapshot_history(
        self,
        session_id: str,
    ) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT *
            FROM pnl_snapshots
            WHERE session_id = ?
            ORDER BY created_at ASC
            """,
            (session_id,),
        )

        return [dict(row) for row in rows]