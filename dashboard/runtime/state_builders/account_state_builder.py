from __future__ import annotations

from typing import Any, Dict

from dashboard.runtime.dashboard_state import DashboardState


class AccountStateBuilder:
    """
    Build account/PnL fields for DashboardState.

    PURPOSE
    -------
    Normalize accounting and PnL outputs into dashboard-safe state.

    RULES
    -----
    - builder must not calculate official accounting truth
    - builder must not override broker/accounting authority
    - builder must not execute trades
    """

    def build(
        self,
        *,
        account_payload: Dict[str, Any],
        state: DashboardState,
    ) -> DashboardState:

        state.cash_balance = float(
            account_payload.get("cash_balance", 0.0)
        )

        state.total_equity = float(
            account_payload.get("total_equity", 0.0)
        )

        state.realized_pnl = float(
            account_payload.get("realized_pnl", 0.0)
        )

        state.unrealized_pnl = float(
            account_payload.get("unrealized_pnl", 0.0)
        )

        state.total_open_positions = int(
            account_payload.get("total_open_positions", 0)
        )

        state.open_positions_by_asset = dict(
            account_payload.get("open_positions_by_asset", {})
        )

        return state