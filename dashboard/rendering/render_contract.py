from __future__ import annotations

from dashboard.runtime.dashboard_state import DashboardState


class DashboardRenderer:
    """
    Canonical dashboard rendering contract.

    PURPOSE
    -------
    Rendering layer only.

    This layer must NOT:
    - compute trading decisions
    - mutate governance state
    - execute trades
    - calculate market intelligence
    - override accounting truth

    It may ONLY:
    - consume DashboardState
    - render structured outputs
    - display summaries
    - format visual presentation
    """

    def render(self, state: DashboardState) -> None:
        """
        Main rendering entrypoint.
        """

        self.render_header(state)

        self.render_governance(state)

        self.render_broker_state(state)

        self.render_market_state(state)

        self.render_asset_summaries(state)

        self.render_positions(state)

        self.render_trade_warehouse(state)

        self.render_footer(state)

    # =====================================================
    # RENDERING SECTIONS
    # =====================================================

    def render_header(self, state: DashboardState) -> None:
        pass

    def render_governance(self, state: DashboardState) -> None:
        pass

    def render_broker_state(self, state: DashboardState) -> None:
        pass

    def render_market_state(self, state: DashboardState) -> None:
        pass

    def render_asset_summaries(self, state: DashboardState) -> None:
        pass

    def render_positions(self, state: DashboardState) -> None:
        pass

    def render_trade_warehouse(self, state: DashboardState) -> None:
        pass

    def render_footer(self, state: DashboardState) -> None:
        pass