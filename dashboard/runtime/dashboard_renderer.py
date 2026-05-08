from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, fields

from dashboard.runtime.dashboard_state import (
    DashboardState,
    GovernanceState,
    MarketStatePayload,
)
from dashboard.runtime.dashboard_shadow_compare import compare_dashboard_shadow
from dashboard.runtime.render_contracts.account_render_contract import AccountRenderContract
from dashboard.runtime.render_contracts.broker_render_contract import (
    BrokerRenderContract,
)
from dashboard.runtime.render_contracts.diagnostics_render_contract import (
    DiagnosticsRenderContract,
)
from dashboard.runtime.render_contracts.governance_render_contract import (
    GovernanceRenderContract,
)
from dashboard.runtime.render_contracts.execution_render_contract import (
    ExecutionRenderContract,
)
from dashboard.runtime.render_contracts.market_render_contract import MarketRenderContract
from dashboard.runtime.render_contracts.pnl_render_contract import PnLRenderContract
from dashboard.runtime.render_contracts.risk_render_contract import RiskRenderContract
from dashboard.runtime.renderers.account_renderer import AccountRenderer
from dashboard.runtime.renderers.broker_renderer import BrokerRenderer
from dashboard.runtime.renderers.diagnostics_renderer import DiagnosticsRenderer
from dashboard.runtime.renderers.execution_renderer import ExecutionRenderer
from dashboard.runtime.renderers.governance_renderer import GovernanceRenderer
from dashboard.runtime.renderers.market_renderer import MarketRenderer
from dashboard.runtime.renderers.pnl_renderer import PnLRenderer
from dashboard.runtime.renderers.risk_renderer import RiskRenderer


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
        self.risk_renderer = RiskRenderer()
        self.execution_renderer = ExecutionRenderer()
        self.broker_renderer = BrokerRenderer()
        self.diagnostics_renderer = DiagnosticsRenderer()

    def render(self, state: DashboardState) -> str:
        runtime_summaries = state.last_scan_results or {}

        account_contract = AccountRenderContract.from_account_state(
            runtime_summaries.get(
                "account_summary",
                {
                    "cash_balance": state.cash_balance,
                    "total_equity": state.total_equity,
                    "currency": getattr(state, "currency", "USD"),
                    "broker": getattr(
                        state.broker_state,
                        "selected_broker",
                        "UNKNOWN",
                    ),
                    "account_mode": state.live_or_paper,
                },
            )
        )

        legacy_pnl_summary = self._legacy_pnl_summary(
            state=state,
            runtime_summaries=runtime_summaries,
        )
        dashboard_state_payload = state.to_dict()
        dashboard_state_pnl_summary = self._mapping_summary(
            dashboard_state_payload.get("pnl_summary", {})
        )
        compare_dashboard_shadow(
            legacy_pnl_summary,
            dashboard_state_pnl_summary,
        )
        migrated_pnl_summary = {
            **legacy_pnl_summary,
            **dashboard_state_pnl_summary,
        }
        pnl_contract = PnLRenderContract.from_summary(
            migrated_pnl_summary
        )

        legacy_market_summary = self._legacy_market_summary(state=state)
        dashboard_state_market_summary = self._mapping_summary(
            dashboard_state_payload.get("market_summary", {})
        )
        compare_dashboard_shadow(
            legacy_market_summary,
            dashboard_state_market_summary,
        )
        migrated_market_summary = {
            **legacy_market_summary,
            **dashboard_state_market_summary,
        }
        market_contract = MarketRenderContract.from_market_state(
            self._market_state_from_summary(migrated_market_summary)
        )

        legacy_governance_summary = self._legacy_governance_summary(
            state=state
        )
        dashboard_state_governance_summary = self._mapping_summary(
            dashboard_state_payload.get("governance_summary", {})
        )
        compare_dashboard_shadow(
            legacy_governance_summary,
            dashboard_state_governance_summary,
        )
        migrated_governance_summary = {
            **legacy_governance_summary,
            **dashboard_state_governance_summary,
        }
        governance_contract = GovernanceRenderContract.from_governance_state(
            self._governance_state_from_summary(
                migrated_governance_summary
            )
        )

        legacy_risk_summary = self._legacy_risk_summary(
            runtime_summaries=runtime_summaries,
        )
        dashboard_state_risk_summary = self._mapping_summary(
            dashboard_state_payload.get("risk_summary", {})
        )
        compare_dashboard_shadow(
            legacy_risk_summary,
            dashboard_state_risk_summary,
        )
        migrated_risk_summary = {
            **legacy_risk_summary,
            **dashboard_state_risk_summary,
        }
        risk_contract = RiskRenderContract.from_summary(
            migrated_risk_summary
        )

        legacy_execution_summary = self._legacy_execution_summary(
            runtime_summaries=runtime_summaries,
        )
        dashboard_state_execution_summary = self._mapping_summary(
            dashboard_state_payload.get("execution_summary", {})
        )
        compare_dashboard_shadow(
            legacy_execution_summary,
            dashboard_state_execution_summary,
        )
        migrated_execution_summary = {
            **legacy_execution_summary,
            **dashboard_state_execution_summary,
        }
        execution_contract = ExecutionRenderContract.from_summary(
            migrated_execution_summary
        )

        legacy_broker_summary = self._legacy_broker_summary(state=state)
        dashboard_state_broker_summary = self._mapping_summary(
            dashboard_state_payload.get("broker_summary", {})
        )
        compare_dashboard_shadow(
            legacy_broker_summary,
            dashboard_state_broker_summary,
        )
        migrated_broker_summary = {
            **legacy_broker_summary,
            **dashboard_state_broker_summary,
        }
        broker_contract = BrokerRenderContract.from_summary(
            migrated_broker_summary
        )
        diagnostics_contract = DiagnosticsRenderContract.from_dashboard_state(
            state
        )
        diagnostics_output = self.diagnostics_renderer.render(
            diagnostics_contract
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
            self.risk_renderer.render(risk_contract),
            "",
            self.execution_renderer.render(execution_contract),
            "",
            self.broker_renderer.render(broker_contract),
            "",
        ]

        if diagnostics_output:
            sections.extend([diagnostics_output, ""])

        sections.append("======================================")

        return "\n".join(sections)

    @staticmethod
    def _legacy_pnl_summary(
        *,
        state: DashboardState,
        runtime_summaries: dict,
    ) -> dict:
        return runtime_summaries.get(
            "pnl_summary",
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
            },
        )

    @staticmethod
    def _legacy_risk_summary(
        *,
        runtime_summaries: dict,
    ) -> dict:
        return runtime_summaries.get(
            "risk_summary",
            {
                "risk_state": "NORMAL",
                "gate_status": "OPEN",
                "total_exposure": 0.0,
                "exposure_utilization_pct": 0.0,
                "current_drawdown_pct": 0.0,
                "max_drawdown_pct": 0.0,
                "daily_loss_limit": 0.0,
                "position_limit": 0,
                "exposure_limit": 0.0,
                "risk_limits_breached": [],
            },
        )

    @staticmethod
    def _legacy_execution_summary(
        *,
        runtime_summaries: dict,
    ) -> dict:
        return runtime_summaries.get(
            "execution_summary",
            {
                "execution_state": "IDLE",
                "accepted_trade_count": 0,
                "rejected_trade_count": 0,
                "pending_trade_count": 0,
                "total_execution_cost": 0.0,
                "slippage_cost": 0.0,
                "spread_cost": 0.0,
                "fee_cost": 0.0,
                "avg_slippage_bps": 0.0,
                "avg_spread_bps": 0.0,
                "execution_cost_state": "UNKNOWN",
                "last_execution_event": "",
            },
        )

    @staticmethod
    def _legacy_market_summary(
        *,
        state: DashboardState,
    ) -> dict:
        return asdict(state.global_market_state)

    @staticmethod
    def _market_state_from_summary(summary: dict) -> MarketStatePayload:
        default_market_state = MarketStatePayload()

        return MarketStatePayload(
            **{
                field.name: summary.get(
                    field.name,
                    getattr(default_market_state, field.name),
                )
                for field in fields(default_market_state)
            }
        )

    @staticmethod
    def _legacy_governance_summary(
        *,
        state: DashboardState,
    ) -> dict:
        return asdict(state.governance_state)

    @staticmethod
    def _legacy_broker_summary(
        *,
        state: DashboardState,
    ) -> dict:
        return asdict(state.broker_state)

    @staticmethod
    def _governance_state_from_summary(summary: dict) -> GovernanceState:
        default_governance_state = GovernanceState()

        return GovernanceState(
            **{
                field.name: summary.get(
                    field.name,
                    getattr(default_governance_state, field.name),
                )
                for field in fields(default_governance_state)
            }
        )

    @staticmethod
    def _mapping_summary(value: object) -> dict:
        if isinstance(value, Mapping):
            return dict(value)

        return {}
