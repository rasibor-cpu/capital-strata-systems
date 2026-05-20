from datetime import datetime
from decimal import Decimal
from typing import Any

from backend.app.persistence.services.persistence_service import (
    PersistenceService,
)


class PnlRuntimeService:
    """
    Runtime PnL snapshot persistence manager.

    Responsibilities:
    - persist account equity snapshots
    - persist cash balance states
    - persist unrealized pnl states
    - provide historical recovery access

    IMPORTANT:
    - no governance logic
    - no orchestration logic
    - no broker execution logic
    """

    def __init__(self) -> None:
        self.persistence = PersistenceService()

    def create_snapshot(
        self,
        session_id: str,
        broker_name: str,
        broker_mode: str,
        equity: Decimal,
        cash_balance: Decimal,
        buying_power: Decimal,
        unrealized_pnl: Decimal,
        realized_pnl: Decimal,
        open_positions: int,
        payload_json: str | None = None,
    ) -> None:

        snapshot_time = (
            datetime.utcnow().isoformat()
        )

        self.persistence.pnl_snapshots.create_snapshot(
            session_id=session_id,
            broker_name=broker_name,
            broker_mode=broker_mode,
            snapshot_time=snapshot_time,
            equity=equity,
            cash_balance=cash_balance,
            buying_power=buying_power,
            unrealized_pnl=unrealized_pnl,
            realized_pnl=realized_pnl,
            open_positions=open_positions,
            payload_json=payload_json,
        )

    def get_latest_snapshot(
        self,
        session_id: str,
    ) -> dict[str, Any] | None:

        return (
            self.persistence.pnl_snapshots
            .get_latest_snapshot(
                session_id=session_id,
            )
        )

    def get_snapshot_history(
        self,
        session_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:

        return (
            self.persistence.pnl_snapshots
            .get_snapshot_history(
                session_id=session_id,
                limit=limit,
            )
        )