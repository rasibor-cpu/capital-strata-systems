from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dashboard.runtime.frontend_contract import DATA_UNAVAILABLE


def build_risk_command_view(state: Mapping[str, Any]) -> dict[str, Any]:
    risk = _mapping(state.get("risk"))
    portfolio = _mapping(state.get("portfolio"))
    return {
        "status": risk.get("overall_risk_state", DATA_UNAVAILABLE),
        "anti_bleed_guard": risk.get("anti_bleed_guard", DATA_UNAVAILABLE),
        "risk_gates": {
            "trade_gate": risk.get("trade_gate_status", DATA_UNAVAILABLE),
            "unified_trade_gate": risk.get("unified_trade_gate", DATA_UNAVAILABLE),
            "margin_gate": risk.get("margin_gate", DATA_UNAVAILABLE),
        },
        "drawdown": risk.get("drawdown", portfolio.get("drawdown", DATA_UNAVAILABLE)),
        "capital_exposure": risk.get("exposure", portfolio.get("total_exposure", DATA_UNAVAILABLE)),
        "margin_utilization": risk.get("collateral_utilization", portfolio.get("collateral_utilization", DATA_UNAVAILABLE)),
        "var": risk.get("var", DATA_UNAVAILABLE),
        "greeks": risk.get("greeks", DATA_UNAVAILABLE),
        "stress_metrics": risk.get("stress_tests", DATA_UNAVAILABLE),
        "kill_switch": risk.get("kill_switch", DATA_UNAVAILABLE),
        "overrides": "DISABLED_READ_ONLY",
        "read_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
        **_metadata(state, "risk_command_view"),
    }


def _metadata(state: Mapping[str, Any], source_module: str) -> dict[str, Any]:
    runtime = _mapping(state.get("runtime"))
    snapshot = _mapping(state.get("runtime_snapshot"))
    freshness = _mapping(state.get("freshness"))
    return {
        "source": runtime.get("source", snapshot.get("source", DATA_UNAVAILABLE)),
        "source_module": f"dashboard.mission_control.{source_module}",
        "provenance": snapshot.get("provenance", {}),
        "generated_at": state.get("generated_at", DATA_UNAVAILABLE),
        "freshness": freshness.get("overall_freshness", DATA_UNAVAILABLE),
        "state_hash": runtime.get("state_hash", snapshot.get("state_hash", DATA_UNAVAILABLE)),
    }


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


__all__ = ["build_risk_command_view"]
