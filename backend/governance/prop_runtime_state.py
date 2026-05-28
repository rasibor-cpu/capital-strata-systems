from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional
import time

from backend.app.accounting.unified_pnl_state import (
    UnifiedPnLState,
)


@dataclass
class PropRuntimeState:

    account_id: str
    evaluation_mode: bool

    starting_balance: float
    current_balance: float
    peak_balance: float

    daily_loss_limit: float
    max_drawdown_limit: float
    trailing_drawdown_limit: float

    realized_pnl: float
    unrealized_pnl: float

    trading_day: str

    last_reset_timestamp: float
    created_timestamp: float
    updated_timestamp: float

    status: str = "ACTIVE"

    # Phase 65B incremental integration
    # PCNRASS-safe:
    # - optional only
    # - preserves existing schema/behavior
    # - no destructive field removal
    unified_pnl_state: Optional[
        UnifiedPnLState
    ] = None

    def total_equity(self) -> float:

        return float(
            self.current_balance
            + self.unrealized_pnl
        )

    def total_pnl(self) -> float:

        return float(
            self.realized_pnl
            + self.unrealized_pnl
        )

    def current_drawdown(self) -> float:

        return float(
            self.peak_balance
            - self.total_equity()
        )

    def trailing_drawdown_breached(
        self,
    ) -> bool:

        return (
            self.current_drawdown()
            >= abs(
                self.trailing_drawdown_limit
            )
        )

    def max_drawdown_breached(
        self,
    ) -> bool:

        return (
            self.current_drawdown()
            >= abs(
                self.max_drawdown_limit
            )
        )

    def daily_loss_breached(
        self,
    ) -> bool:

        return (
            self.total_pnl()
            <= (
                -1.0
                * abs(
                    self.daily_loss_limit
                )
            )
        )

    def sync_from_unified_pnl_state(
        self,
    ) -> None:

        if self.unified_pnl_state is None:
            return

        pnl_state = self.unified_pnl_state

        self.current_balance = float(
            pnl_state.cash_balance
        )

        self.realized_pnl = float(
            pnl_state.realized_pnl
        )

        self.unrealized_pnl = float(
            pnl_state.unrealized_pnl
        )

        current_equity = (
            pnl_state.total_equity()
        )

        if current_equity > self.peak_balance:
            self.peak_balance = float(
                current_equity
            )

        self.updated_timestamp = (
            time.time()
        )

    def update_equity(
        self,
        realized_pnl: float,
        unrealized_pnl: float,
        current_balance: float,
    ) -> None:

        self.realized_pnl = float(
            realized_pnl
        )

        self.unrealized_pnl = float(
            unrealized_pnl
        )

        self.current_balance = float(
            current_balance
        )

        equity = self.total_equity()

        if equity > self.peak_balance:
            self.peak_balance = equity

        self.updated_timestamp = (
            time.time()
        )

    def governance_snapshot(
        self,
    ) -> Dict[str, Any]:

        snapshot = {
            "status": self.status,
            "evaluation_mode": (
                self.evaluation_mode
            ),
            "current_balance": (
                self.current_balance
            ),
            "peak_balance": (
                self.peak_balance
            ),
            "total_equity": (
                self.total_equity()
            ),
            "total_pnl": (
                self.total_pnl()
            ),
            "current_drawdown": (
                self.current_drawdown()
            ),
            "daily_loss_breached": (
                self.daily_loss_breached()
            ),
            "max_drawdown_breached": (
                self.max_drawdown_breached()
            ),
            "trailing_drawdown_breached": (
                self.trailing_drawdown_breached()
            ),
            "updated_timestamp": (
                self.updated_timestamp
            ),
        }

        if self.unified_pnl_state is not None:

            snapshot[
                "unified_pnl_snapshot"
            ] = (
                self.unified_pnl_state
                .governance_snapshot()
            )

        return snapshot

    def as_dict(
        self,
    ) -> Dict[str, Any]:

        return asdict(self)


def build_default_runtime_state(
) -> PropRuntimeState:

    now = time.time()

    return PropRuntimeState(
        account_id="SIM-ACCOUNT",
        evaluation_mode=True,
        starting_balance=100000.0,
        current_balance=100000.0,
        peak_balance=100000.0,
        daily_loss_limit=2500.0,
        max_drawdown_limit=5000.0,
        trailing_drawdown_limit=3500.0,
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        trading_day="",
        last_reset_timestamp=now,
        created_timestamp=now,
        updated_timestamp=now,
        status="ACTIVE",
        unified_pnl_state=None,
    )


__all__ = [
    "PropRuntimeState",
    "build_default_runtime_state",
]
