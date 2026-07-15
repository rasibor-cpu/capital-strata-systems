from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dashboard.runtime.frontend_contract import DATA_UNAVAILABLE


def build_capital_committee_panel(state: Mapping[str, Any]) -> dict[str, Any]:
    capital = _mapping(state.get("capital_allocation_center"))
    portfolio = _mapping(state.get("portfolio"))
    return {
        "status": "FAIL_CLOSED" if _runtime_unavailable(state) else capital.get("status", DATA_UNAVAILABLE),
        "capital_efficiency": portfolio.get("capital_efficiency", DATA_UNAVAILABLE),
        "unused_capital": capital.get("available_capital", DATA_UNAVAILABLE),
        "deployment_efficiency": capital.get("utilization", DATA_UNAVAILABLE),
        "cash_utilization": portfolio.get("cash", DATA_UNAVAILABLE),
        "margin_utilization": portfolio.get("collateral_utilization", DATA_UNAVAILABLE),
        "portfolio_leverage": portfolio.get("leverage", DATA_UNAVAILABLE),
        "allocation_summary": {
            "strategy": capital.get("strategy_allocation", {}),
            "asset": capital.get("asset_allocation", {}),
            "currency": capital.get("currency_allocation", DATA_UNAVAILABLE),
        },
        "links": _links("portfolio", "risk_command", "learning_performance"),
        "read_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
        **_metadata(state, "capital_committee"),
    }


def _links(*keys: str) -> list[dict[str, str]]:
    return [{"label": key.replace("_", " ").title(), "route": f"/mission-control/{key.replace('_', '-')}"} for key in keys]


def _metadata(state: Mapping[str, Any], source_module: str) -> dict[str, Any]:
    runtime = _mapping(state.get("runtime"))
    snapshot = _mapping(state.get("runtime_snapshot"))
    freshness = _mapping(state.get("freshness"))
    decision = _mapping(state.get("decision_panel"))
    return {
        "source": runtime.get("source", snapshot.get("source", DATA_UNAVAILABLE)),
        "source_module": f"dashboard.mission_control.{source_module}",
        "provenance": snapshot.get("provenance", {}),
        "generated_at": state.get("generated_at", DATA_UNAVAILABLE),
        "freshness": freshness.get("overall_freshness", DATA_UNAVAILABLE),
        "runtime_id": runtime.get("runtime_id", snapshot.get("runtime_id", DATA_UNAVAILABLE)),
        "state_hash": runtime.get("state_hash", snapshot.get("state_hash", DATA_UNAVAILABLE)),
        "decision_hash": decision.get("state_hash", DATA_UNAVAILABLE),
    }


def _runtime_unavailable(state: Mapping[str, Any]) -> bool:
    runtime = _mapping(state.get("runtime"))
    return str(runtime.get("runtime_status", "")).upper() in {"OFFLINE", "UNAVAILABLE"} or str(runtime.get("source", "")).upper() in {"", "UNAVAILABLE", "UNKNOWN"}


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


__all__ = ["build_capital_committee_panel"]
