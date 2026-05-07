from __future__ import annotations

from dashboard.runtime.dashboard_state import DashboardState
from dashboard.runtime.render_contracts.account_render_contract import AccountRenderContract
from dashboard.runtime.render_contracts.governance_render_contract import (
    GovernanceRenderContract,
)
from dashboard.runtime.render_contracts.market_render_contract import MarketRenderContract
from dashboard.runtime.render_contracts.pnl_render_contract import PnLRenderContract
from dashboard.runtime.renderers.account_renderer import AccountRenderer
from dashboard.runtime.renderers.governance_renderer import GovernanceRenderer
from dashboard.runtime.renderers.market_renderer import MarketRenderer
from dashboard.runtime.renderers.pnl_renderer import PnLRenderer


class DashboardRenderer:
    """
    PCNRASS-safe dashboard renderer orchestrator.

    Purpose:
    - Compose dashboard output from canonical DashboardState.
    - Build immutable render contracts.
    - Delegate formatting to pure renderers.
    - Keep business logic outside the rendering layer.
    """

    def __init__(self) -> None:
        self.account_renderer = AccountRenderer()
        self.pnl_renderer = PnLRenderer()
        self.market_renderer = MarketRenderer()
        self.governance_renderer = GovernanceRenderer()

    def render(self, state: DashboardState) -> str:
        account_contract = AccountRenderContract.from_account_state(
            {
                "cash_balance": state.cash_balance,
                "total_equity": state.total_equity,
                "currency": getattr(state, "currency", "USD"),
                "broker": getattr(state.broker_state, "selected_broker", "UNKNOWN"),
                "account_mode": state.live_or_paper,
            }
        )

        pnl_contract = PnLRenderContract.from_summary(
            {
                "realized_pnl": state.realized_pnl,
                "unrealized_pnl": state.unrealized_pnl,
                "net_pnl": state.realized_pnl + state.unrealized_pnl,
                "total_exposure": 0.0,
                "exposure_utilization_pct": 0.0,
                "winner_count": 0,
                "loser_count": 0,
                "win_rate_pct": 0.0,
                "account_equity": state.total_equity,
                "asset_realized_pnl": {},
                "asset_unrealized_pnl": {},
            }
        )

        market_contract = MarketRenderContract.from_market_state(
            state.global_market_state
        )

        governance_contract = GovernanceRenderContract.from_governance_state(
            state.governance_state
        )

        sections = [
            "======================================",
            " CAPITAL STRATA SYSTEMS DASHBOARD",
            "======================================",
            f"Session ID:     {state.session_id}",
            f"User ID:        {state.user_id}",
            f"Role:           {state.role}",
            f"Cycle:          {state.cycle_number}",
            f"Engine Mode:    {state.engine_mode}",
            f"Runtime Mode:   {state.live_or_paper}",
            "",
            self.account_renderer.render(account_contract),
            "",
            self.pnl_renderer.render(pnl_contract),
            "",
            self.market_renderer.render(market_contract),
            "",
            self.governance_renderer.render(governance_contract),
            "",
            "======================================",
        ]

        return "\n".join(sections)
