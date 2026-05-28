from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Any
import time


@dataclass
class UnifiedPnLState:

    account_id: str

    starting_balance: float

    cash_balance: float

    realized_pnl: float
    unrealized_pnl: float

    peak_equity: float

    open_positions: int

    total_trades: int
    winning_trades: int
    losing_trades: int

    created_timestamp: float
    updated_timestamp: float

    status: str = "ACTIVE"

    def total_equity(self) -> float:

        return float(
            self.cash_balance
            + self.unrealized_pnl
        )

    def total_pnl(self) -> float:

        return float(
            self.realized_pnl
            + self.unrealized_pnl
        )

    def current_drawdown(self) -> float:

        return float(
            self.peak_equity
            - self.total_equity()
        )

    def profit_factor(self) -> float:

        gross_profit = max(
            self.realized_pnl,
            0.0,
        )

        gross_loss = abs(
            min(
                self.realized_pnl,
                0.0,
            )
        )

        if gross_loss <= 0:
            return float(gross_profit)

        return float(
            gross_profit
            / gross_loss
        )

    def win_rate(self) -> float:

        if self.total_trades <= 0:
            return 0.0

        return float(
            self.winning_trades
            / self.total_trades
        )

    def update_runtime_state(
        self,
        cash_balance: float,
        realized_pnl: float,
        unrealized_pnl: float,
        open_positions: int,
        total_trades: int,
        winning_trades: int,
        losing_trades: int,
    ) -> None:

        self.cash_balance = float(
            cash_balance
        )

        self.realized_pnl = float(
            realized_pnl
        )

        self.unrealized_pnl = float(
            unrealized_pnl
        )

        self.open_positions = int(
            open_positions
        )

        self.total_trades = int(
            total_trades
        )

        self.winning_trades = int(
            winning_trades
        )

        self.losing_trades = int(
            losing_trades
        )

        equity = self.total_equity()

        if equity > self.peak_equity:
            self.peak_equity = equity

        self.updated_timestamp = time.time()

    def governance_snapshot(self) -> Dict[str, Any]:

        return {
            "status": self.status,
            "cash_balance": (
                self.cash_balance
            ),
            "realized_pnl": (
                self.realized_pnl
            ),
            "unrealized_pnl": (
                self.unrealized_pnl
            ),
            "total_pnl": (
                self.total_pnl()
            ),
            "total_equity": (
                self.total_equity()
            ),
            "peak_equity": (
                self.peak_equity
            ),
            "current_drawdown": (
                self.current_drawdown()
            ),
            "profit_factor": (
                self.profit_factor()
            ),
            "win_rate": (
                self.win_rate()
            ),
            "open_positions": (
                self.open_positions
            ),
            "total_trades": (
                self.total_trades
            ),
            "updated_timestamp": (
                self.updated_timestamp
            ),
        }

    def as_dict(self) -> Dict[str, Any]:

        return asdict(self)


def build_default_unified_pnl_state() -> UnifiedPnLState:

    now = time.time()

    return UnifiedPnLState(
        account_id="SIM-ACCOUNT",
        starting_balance=100000.0,
        cash_balance=100000.0,
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        peak_equity=100000.0,
        open_positions=0,
        total_trades=0,
        winning_trades=0,
        losing_trades=0,
        created_timestamp=now,
        updated_timestamp=now,
        status="ACTIVE",
    )


__all__ = [
    "UnifiedPnLState",
    "build_default_unified_pnl_state",
]
