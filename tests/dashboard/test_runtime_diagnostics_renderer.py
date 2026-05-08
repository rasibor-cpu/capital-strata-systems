from __future__ import annotations

from dashboard.runtime.dashboard_state import DashboardState
from dashboard.runtime.render_contracts.diagnostics_render_contract import (
    DiagnosticsRenderContract,
)
from dashboard.runtime.renderers.diagnostics_renderer import DiagnosticsRenderer


def test_diagnostics_renderer_returns_empty_output_without_items() -> None:
    state = DashboardState(
        session_id="SESSION",
        user_id="user",
    )
    state.broker_state.selected_broker = "DEMO"
    state.last_scan_results = {
        "account_summary": {"total_equity": 100.0},
        "pnl_summary": {"net_pnl": 0.0},
        "risk_summary": {"risk_state": "NORMAL"},
        "execution_summary": {"execution_state": "READY"},
    }

    contract = DiagnosticsRenderContract.from_dashboard_state(state)

    assert contract.has_items() is False
    assert DiagnosticsRenderer().render(contract) == ""


def test_diagnostics_contract_reports_hydration_gaps_and_governance_alerts() -> None:
    state = DashboardState()
    state.governance_state.session_locked = True
    state.governance_state.defensive_mode_active = True

    contract = DiagnosticsRenderContract.from_dashboard_state(state)
    output = DiagnosticsRenderer().render(contract)

    assert "RUNTIME DIAGNOSTICS" in output
    assert "Missing account_summary" in output
    assert "Missing session_id" in output
    assert "Session locked" in output
    assert "Defensive mode active" in output


def test_diagnostics_contract_deduplicates_messages() -> None:
    state = DashboardState(
        session_id="SESSION",
        user_id="user",
    )
    state.broker_state.selected_broker = "DEMO"
    state.last_scan_results = {
        "account_summary": {"total_equity": 100.0},
        "pnl_summary": {"net_pnl": 0.0},
        "risk_summary": {"risk_state": "NORMAL"},
        "execution_summary": {"execution_state": "READY"},
        "diagnostics_summary": {
            "messages": ["ready", "ready"],
            "warnings": ["watch", "watch"],
        },
    }

    contract = DiagnosticsRenderContract.from_dashboard_state(state)

    assert contract.messages == ("ready",)
    assert contract.warnings == ("watch",)
