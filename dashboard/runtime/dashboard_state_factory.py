from __future__ import annotations

from typing import Any, Dict

from dashboard.runtime.dashboard_state import DashboardState
from dashboard.runtime.state_builders.account_state_builder import AccountStateBuilder
from dashboard.runtime.state_builders.broker_state_builder import BrokerStateBuilder
from dashboard.runtime.state_builders.governance_state_builder import GovernanceStateBuilder
from dashboard.runtime.state_builders.market_state_builder import MarketStateBuilder
from dashboard.runtime.state_builders.position_state_builder import PositionStateBuilder
from dashboard.runtime.summary_builders.execution_summary_builder import (
    ExecutionSummaryBuilder,
)
from dashboard.runtime.summary_builders.pnl_summary_builder import PnLSummaryBuilder
from dashboard.runtime.summary_builders.risk_summary_builder import RiskSummaryBuilder


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
        self.broker_builder = BrokerStateBuilder()
        self.governance_builder = GovernanceStateBuilder()
        self.market_builder = MarketStateBuilder()
        self.position_builder = PositionStateBuilder()
        self.risk_summary_builder = RiskSummaryBuilder()
        self.execution_summary_builder = ExecutionSummaryBuilder()
        self.pnl_summary_builder = PnLSummaryBuilder()

    def build(
        self,
        account_payload: Dict[str, Any] | None = None,
        broker_payload: Dict[str, Any] | None = None,
        positions_payload: Dict[str, Any] | None = None,
        market_payload: Dict[str, Any] | None = None,
        governance_payload: Dict[str, Any] | None = None,
        risk_payload: Dict[str, Any] | None = None,
        execution_payload: Dict[str, Any] | None = None,
        session_payload: Dict[str, Any] | None = None,
        diagnostics_payload: Dict[str, Any] | None = None,
    ) -> DashboardState:

        dashboard_state = DashboardState()
        account = account_payload or {}

        dashboard_state = self.account_builder.build(
            account_payload=account,
            state=dashboard_state,
        )

        broker = broker_payload or {
            "selected_broker": account.get(
                "selected_broker",
                account.get("broker", "NONE"),
            ),
            "broker_mode": account.get(
                "broker_mode",
                account.get("account_mode", "paper"),
            ),
            "connected": account.get("connected", False),
            "live_trading_enabled": account.get("live_trading_enabled", False),
            "last_heartbeat": account.get("last_heartbeat", ""),
        }

        dashboard_state = self.broker_builder.build(
            broker_payload=broker,
            state=dashboard_state,
        )

        dashboard_state = self.market_builder.build(
            market_payload=market_payload or {},
            state=dashboard_state,
        )

        dashboard_state = self.governance_builder.build(
            governance_payload=governance_payload or {},
            state=dashboard_state,
        )

        position_state = self.position_builder.build(
            positions_payload or {}
        )

        account_summary_state = {
            "cash_balance": dashboard_state.cash_balance,
            "total_equity": dashboard_state.total_equity,
            "equity": dashboard_state.total_equity,
            "balance": dashboard_state.cash_balance,
            "buying_power": account.get("buying_power", 0.0),
            "margin_used": account.get("margin_used", 0.0),
            "available_margin": account.get("available_margin", 0.0),
            "currency": account.get("currency", "USD"),
            "broker": dashboard_state.broker_state.selected_broker,
            "account_mode": dashboard_state.broker_state.broker_mode,
        }

        pnl_summary = self.pnl_summary_builder.build(
            account_state=account_summary_state,
            position_state=position_state,
        )

        risk_summary = self.risk_summary_builder.build(
            account_state=account_summary_state,
            position_state=position_state,
            risk_payload=risk_payload,
        )

        execution_summary = self.execution_summary_builder.build(
            execution_payload=execution_payload,
        )
        execution_history = self._execution_history(execution_payload or {})

        dashboard_state.last_scan_results["account_summary"] = account_summary_state
        dashboard_state.last_scan_results["position_state"] = position_state
        dashboard_state.last_scan_results["pnl_summary"] = pnl_summary
        dashboard_state.last_scan_results["risk_summary"] = risk_summary
        dashboard_state.last_scan_results["execution_summary"] = execution_summary
        dashboard_state.last_scan_results["execution_history"] = execution_history

        dashboard_state.realized_pnl = float(
            pnl_summary.get("realized_pnl", dashboard_state.realized_pnl)
        )

        dashboard_state.unrealized_pnl = float(
            pnl_summary.get("unrealized_pnl", dashboard_state.unrealized_pnl)
        )

        dashboard_state.total_open_positions = int(
            position_state.get("open_count", dashboard_state.total_open_positions)
        )

        dashboard_state.open_positions_by_asset = dict(
            position_state.get(
                "asset_counts",
                dashboard_state.open_positions_by_asset,
            )
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

    @staticmethod
    def _execution_history(execution_payload: Dict[str, Any]) -> list[dict[str, Any]]:
        raw_history = execution_payload.get(
            "execution_history",
            execution_payload.get("recent_trades", []),
        )

        if not isinstance(raw_history, list):
            return []

        return [
            dict(item)
            for item in raw_history
            if isinstance(item, dict)
        ]
