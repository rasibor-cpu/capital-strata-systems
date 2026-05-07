from __future__ import annotations

import contextlib
import io
from typing import Any, Dict, List

from dashboard.runtime.dashboard_hydration_coordinator import (
    DashboardHydrationCoordinator,
)
from dashboard.runtime.dashboard_renderer import DashboardRenderer
from dashboard.runtime.dashboard_state import DashboardState
from dashboard.runtime.demo_runtime_runner import main as demo_main
from dashboard.runtime.render_contracts.account_render_contract import (
    AccountRenderContract,
)
from dashboard.runtime.render_contracts.execution_render_contract import (
    ExecutionRenderContract,
)
from dashboard.runtime.render_contracts.governance_render_contract import (
    GovernanceRenderContract,
)
from dashboard.runtime.render_contracts.market_render_contract import (
    MarketRenderContract,
)
from dashboard.runtime.render_contracts.pnl_render_contract import PnLRenderContract
from dashboard.runtime.render_contracts.risk_render_contract import RiskRenderContract
from dashboard.runtime.renderers.account_renderer import AccountRenderer
from dashboard.runtime.renderers.execution_renderer import ExecutionRenderer
from dashboard.runtime.renderers.governance_renderer import GovernanceRenderer
from dashboard.runtime.renderers.market_renderer import MarketRenderer
from dashboard.runtime.renderers.pnl_renderer import PnLRenderer
from dashboard.runtime.renderers.risk_renderer import RiskRenderer
from dashboard.runtime.runtime_bootstrap import DashboardRuntimeBootstrap
from dashboard.runtime.state_builders.account_state_builder import AccountStateBuilder
from dashboard.runtime.state_builders.broker_state_builder import BrokerStateBuilder
from dashboard.runtime.state_builders.governance_state_builder import (
    GovernanceStateBuilder,
)
from dashboard.runtime.state_builders.market_state_builder import MarketStateBuilder
from dashboard.runtime.state_builders.position_state_builder import PositionStateBuilder
from dashboard.runtime.summary_builders.execution_summary_builder import (
    ExecutionSummaryBuilder,
)
from dashboard.runtime.summary_builders.pnl_summary_builder import PnLSummaryBuilder
from dashboard.runtime.summary_builders.risk_summary_builder import RiskSummaryBuilder


def build_smoke_payloads() -> Dict[str, Dict[str, Any]]:
    return {
        "account_payload": {
            "cash_balance": 10000.00,
            "total_equity": 10250.00,
            "buying_power": 5000.00,
            "margin_used": 1000.00,
            "available_margin": 4000.00,
            "currency": "USD",
            "broker": "DEMO",
            "account_mode": "paper",
        },
        "positions_payload": {
            "positions": [
                {
                    "symbol": "BTC-USD",
                    "asset_class": "CRYPTO",
                    "side": "LONG",
                    "qty": 0.05,
                    "entry_price": 65000.00,
                    "current_price": 65500.00,
                    "unrealized_pnl": 25.00,
                    "realized_pnl": 0.00,
                },
                {
                    "symbol": "EUR_USD",
                    "asset_class": "FX",
                    "side": "SHORT",
                    "qty": 1000,
                    "entry_price": 1.0900,
                    "current_price": 1.0875,
                    "unrealized_pnl": 2.50,
                    "realized_pnl": 0.00,
                },
            ],
        },
        "market_payload": {
            "trend_state": "UPTREND",
            "volatility_state": "NORMAL",
            "liquidity_state": "HEALTHY",
            "mean_reversion_state": "NEUTRAL",
            "probability_state": "FAVORABLE",
            "velocity_state": "RISING",
            "vwap_state": "ABOVE_VWAP",
            "vwap_distance": 0.0125,
            "vwap_elasticity": 0.8300,
            "momentum_state": "POSITIVE",
            "pressure_state": "BUY_PRESSURE",
            "acceleration_state": "STABLE",
            "regime_state": "RISK_ON",
            "spread_state": "TIGHT",
            "execution_cost_state": "ACCEPTABLE",
            "signal_confluence_state": "CONFIRMED",
        },
        "governance_payload": {
            "governance_enabled": True,
            "session_locked": False,
            "defensive_mode_active": False,
            "unified_trade_gate_active": True,
            "audit_enabled": True,
            "last_governance_event": "Smoke governance state hydrated",
        },
        "risk_payload": {
            "risk_state": "NORMAL",
            "gate_status": "OPEN",
            "current_drawdown_pct": 0.35,
            "max_drawdown_pct": 2.00,
            "daily_loss_limit": 500.00,
            "position_limit": 10,
            "exposure_limit": 25000.00,
            "risk_limits_breached": [],
        },
        "execution_payload": {
            "execution_state": "READY",
            "accepted_trade_count": 2,
            "rejected_trade_count": 0,
            "pending_trade_count": 0,
            "total_execution_cost": 1.25,
            "slippage_cost": 0.50,
            "spread_cost": 0.45,
            "fee_cost": 0.30,
            "avg_slippage_bps": 1.20,
            "avg_spread_bps": 0.80,
            "execution_cost_state": "ACCEPTABLE",
            "last_execution_event": "Smoke execution summary hydrated",
        },
        "session_payload": {
            "session_id": "SMOKE-SESSION",
            "user_id": "smoke_user",
            "role": "TRADER",
            "cycle_number": 1,
            "engine_mode": "SAFE",
            "live_or_paper": "paper",
        },
        "diagnostics_payload": {
            "message": "Smoke runtime validation successful",
        },
    }


def require(condition: bool, message: str, failures: List[str]) -> None:
    if not condition:
        failures.append(message)


def validate_builders(payloads: Dict[str, Dict[str, Any]], failures: List[str]) -> None:
    state = DashboardState()

    state = AccountStateBuilder().build(
        account_payload=payloads["account_payload"],
        state=state,
    )
    state = BrokerStateBuilder().build(
        broker_payload={
            "selected_broker": "DEMO",
            "broker_mode": "paper",
        },
        state=state,
    )
    state = MarketStateBuilder().build(
        market_payload=payloads["market_payload"],
        state=state,
    )
    state = GovernanceStateBuilder().build(
        governance_payload=payloads["governance_payload"],
        state=state,
    )
    position_state = PositionStateBuilder().build(payloads["positions_payload"])
    pnl_summary = PnLSummaryBuilder().build(
        account_state={
            "equity": state.total_equity,
            "balance": state.cash_balance,
        },
        position_state=position_state,
    )
    risk_summary = RiskSummaryBuilder().build(
        account_state={
            "equity": state.total_equity,
            "balance": state.cash_balance,
        },
        position_state=position_state,
        risk_payload=payloads["risk_payload"],
    )
    execution_summary = ExecutionSummaryBuilder().build(
        execution_payload=payloads["execution_payload"],
    )

    require(state.cash_balance == 10000.00, "account builder cash mismatch", failures)
    require(
        state.broker_state.selected_broker == "DEMO",
        "broker builder selected broker mismatch",
        failures,
    )
    require(
        state.global_market_state.trend_state == "UPTREND",
        "market builder trend mismatch",
        failures,
    )
    require(
        state.governance_state.governance_enabled is True,
        "governance builder enabled mismatch",
        failures,
    )
    require(position_state["open_count"] == 2, "position builder count mismatch", failures)
    require(
        pnl_summary["unrealized_pnl"] == 27.50,
        "PnL summary unrealized mismatch",
        failures,
    )
    require(risk_summary["risk_state"] == "NORMAL", "risk summary mismatch", failures)
    require(
        execution_summary["execution_state"] == "READY",
        "execution summary mismatch",
        failures,
    )


def validate_hydration_and_rendering(
    payloads: Dict[str, Dict[str, Any]],
    failures: List[str],
) -> None:
    state = DashboardHydrationCoordinator().hydrate(**payloads)
    output = DashboardRenderer().render(state)

    require(state.session_id == "SMOKE-SESSION", "session hydration mismatch", failures)
    require(state.total_open_positions == 2, "open position hydration mismatch", failures)
    require(
        state.last_scan_results["execution_summary"]["execution_state"] == "READY",
        "execution hydration mismatch",
        failures,
    )

    for expected in [
        "ACCOUNT SUMMARY",
        "PnL SUMMARY",
        "MARKET INTELLIGENCE",
        "GOVERNANCE STATE",
        "RISK SUMMARY",
        "EXECUTION SUMMARY",
    ]:
        require(expected in output, f"missing rendered section: {expected}", failures)

    account_contract = AccountRenderContract.from_account_state(
        state.last_scan_results["account_summary"]
    )
    pnl_contract = PnLRenderContract.from_summary(
        state.last_scan_results["pnl_summary"]
    )
    market_contract = MarketRenderContract.from_market_state(
        state.global_market_state
    )
    governance_contract = GovernanceRenderContract.from_governance_state(
        state.governance_state
    )
    risk_contract = RiskRenderContract.from_summary(
        state.last_scan_results["risk_summary"]
    )
    execution_contract = ExecutionRenderContract.from_summary(
        state.last_scan_results["execution_summary"]
    )

    renderer_outputs = [
        AccountRenderer().render(account_contract),
        PnLRenderer().render(pnl_contract),
        MarketRenderer().render(market_contract),
        GovernanceRenderer().render(governance_contract),
        RiskRenderer().render(risk_contract),
        ExecutionRenderer().render(execution_contract),
    ]

    for renderer_output in renderer_outputs:
        require(bool(renderer_output.strip()), "renderer produced empty output", failures)


def validate_bootstrap(payloads: Dict[str, Dict[str, Any]], failures: List[str]) -> None:
    output = DashboardRuntimeBootstrap().run(**payloads)

    for expected in [
        "SMOKE-SESSION",
        "Broker:                  DEMO",
        "Trend State:             UPTREND",
        "Risk State:              NORMAL",
        "Execution State:         READY",
    ]:
        require(expected in output, f"bootstrap output missing: {expected}", failures)


def validate_demo_runner(failures: List[str]) -> None:
    buffer = io.StringIO()

    with contextlib.redirect_stdout(buffer):
        demo_main()

    output = buffer.getvalue()

    for expected in [
        "CAPITAL STRATA SYSTEMS DASHBOARD",
        "ACCOUNT SUMMARY",
        "MARKET INTELLIGENCE",
        "GOVERNANCE STATE",
        "RISK SUMMARY",
        "EXECUTION SUMMARY",
    ]:
        require(expected in output, f"demo runner missing: {expected}", failures)


def main() -> int:
    failures: List[str] = []
    payloads = build_smoke_payloads()

    validate_builders(payloads, failures)
    validate_hydration_and_rendering(payloads, failures)
    validate_bootstrap(payloads, failures)
    validate_demo_runner(failures)

    if failures:
        print("CSS runtime smoke test FAILED")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("CSS runtime smoke test PASSED")
    print("Validated: imports, builders, contracts, renderers, bootstrap, demo runner")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
