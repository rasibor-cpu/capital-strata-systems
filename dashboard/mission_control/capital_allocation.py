from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dashboard.runtime.frontend_contract import DATA_UNAVAILABLE


def build_capital_allocation_center(state: Mapping[str, Any]) -> dict[str, Any]:
    source = _institutional_source(state, "capital_allocation")
    portfolio = _mapping(state.get("portfolio"))
    command = _mapping(state.get("portfolio_command"))
    return {
        "status": "FAIL_CLOSED" if _runtime_unavailable(state) else command.get("status", "UNAVAILABLE"),
        "capital_deployed": source.get("capital_deployed", command.get("deployed_capital", portfolio.get("capital_deployed", DATA_UNAVAILABLE))),
        "available_capital": source.get("available_capital", command.get("available_capital", portfolio.get("capital_available", DATA_UNAVAILABLE))),
        "reserved_capital": source.get("reserved_capital", DATA_UNAVAILABLE),
        "utilization": source.get("utilization", command.get("capital_utilization", DATA_UNAVAILABLE)),
        "strategy_allocation": source.get("strategy_allocation", source.get("strategy_allocations", {})),
        "asset_allocation": source.get("asset_allocation", portfolio.get("asset_allocation", {})),
        "sector_allocation": source.get("sector_allocation", portfolio.get("sector_allocation", DATA_UNAVAILABLE)),
        "currency_allocation": source.get("currency_allocation", portfolio.get("currency_exposure", DATA_UNAVAILABLE)),
        "institution_allocation": source.get("institution_allocation", DATA_UNAVAILABLE),
        "links": _links("portfolio", "learning_performance", "risk_command"),
        "read_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
        **_metadata(state, "capital_allocation"),
    }


def _institutional_source(state: Mapping[str, Any], key: str) -> dict[str, Any]:
    sources = _mapping(state.get("institutional_sources"))
    return _mapping(sources.get(key))


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


__all__ = ["build_capital_allocation_center"]
