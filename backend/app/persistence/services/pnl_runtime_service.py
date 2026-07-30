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
        account_id: str | None = None,
        available_cash: Decimal | None = None,
        winning_positions: int = 0,
        losing_positions: int = 0,
        snapshot_reason: str | None = None,
        payload_json: str | None = None,
        equity_peak: Decimal | None = None,
    ) -> None:
        del buying_power, payload_json

        resolved_account_id = (
            str(account_id).strip()
            if account_id is not None and str(account_id).strip()
            else f"{broker_name.upper()}-{broker_mode.upper()}"
        )

        resolved_available_cash = (
            available_cash
            if available_cash is not None
            else cash_balance
        )

        # RR-001: when peak is omitted, default to equity (never silently drop peak).
        resolved_equity_peak = equity if equity_peak is None else equity_peak

        self.persistence.pnl_snapshots.create_snapshot(
            session_id=session_id,
            account_id=resolved_account_id,
            broker_name=broker_name,
            broker_mode=broker_mode,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            equity=equity,
            equity_peak=resolved_equity_peak,
            available_cash=resolved_available_cash,
            open_positions=open_positions,
            winning_positions=int(winning_positions),
            losing_positions=int(losing_positions),
            snapshot_reason=snapshot_reason,
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
