from __future__ import annotations

from typing import Any, Dict

from dashboard.runtime.dashboard_state import DashboardState
from dashboard.runtime.state_builders.account_state_builder import AccountStateBuilder
from dashboard.runtime.state_builders.position_state_builder import PositionStateBuilder
from dashboard.runtime.summary_builders.pnl_summary_builder import PnLSummaryBuilder


class DashboardStateFactory:
    """
    PCNRASS-safe DashboardState assembly factory.

    Purpose:
    - Assemble normalized dashboard state from runtime payloads.
    - Keep renderers independent from raw engine/account/position payloads.
    - Centralize builder sequencing in one auditable location.
    """

    def __init__(self) -> None:
        self.account_builder = AccountStateBuilder()
        self.position_builder = PositionStateBuilder()
        self.pnl_summary_builder = PnLSummaryBuilder()

    def build(
        self,
        account_payload: Dict[str, Any] | None = None,
        positions_payload: Dict[str, Any] | None = None,
        session_payload: Dict[str, Any] | None = None,
        diagnostics_payload: Dict[str, Any] | None = None,
    ) -> DashboardState:

        account_state = self.account_builder.build(account_payload)
        position_state = self.position_builder.build(positions_payload)

        pnl_summary = self.pnl_summary_builder.build(
            account_state=account_state,
            position_state=position_state,
        )

        dashboard_state = DashboardState()

        dashboard_state.cash_balance = float(
            account_state.get("cash_balance", account_state.get("balance", 0.0))
        )

        dashboard_state.total_equity = float(
            account_state.get("total_equity", account_state.get("equity", 0.0))
        )

        dashboard_state.realized_pnl = float(
            pnl_summary.get("realized_pnl", 0.0)
        )

        dashboard_state.unrealized_pnl = float(
            pnl_summary.get("unrealized_pnl", 0.0)
        )

        dashboard_state.total_open_positions = int(
            position_state.get("open_count", 0)
        )

        dashboard_state.open_positions_by_asset = dict(
            position_state.get("asset_counts", {})
        )

        session = session_payload or {}

        dashboard_state.session_id = str(session.get("session_id", ""))
        dashboard_state.user_id = str(session.get("user_id", ""))
        dashboard_state.role = str(session.get("role", "TRADER"))
        dashboard_state.cycle_number = int(session.get("cycle_number", 0))
        dashboard_state.engine_mode = str(session.get("engine_mode", "SAFE"))
        dashboard_state.live_or_paper = str(session.get("live_or_paper", "paper"))

        diagnostics = diagnostics_payload or {}

        if diagnostics:
            dashboard_state.dashboard_messages.append(
                str(diagnostics.get("message", "Diagnostics payload received"))
            )

        return dashboard_state