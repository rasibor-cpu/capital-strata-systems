from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dashboard.runtime.frontend_contract import DATA_UNAVAILABLE


def build_strategy_war_room(state: Mapping[str, Any]) -> dict[str, Any]:
    source = _institutional_source(state, "analytics")
    learning = _mapping(state.get("learning"))
    rows = _rows(source, "strategies", "strategy_rankings", fallback=learning.get("strategy_rankings", []))
    strategies = [_strategy(state, item, index) for index, item in enumerate(rows, start=1)]
    status = "FAIL_CLOSED" if _runtime_unavailable(state) else "AVAILABLE" if strategies else "UNAVAILABLE"
    return {
        "status": status,
        "strategies": strategies,
        "strategy_count": len(strategies),
        "links": _links("learning_performance", "portfolio", "risk_command"),
        "read_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
        **_metadata(state, "strategy_war_room"),
    }


def _strategy(state: Mapping[str, Any], item: Any, rank: int) -> dict[str, Any]:
    payload = _mapping(item)
    if not payload:
        payload = {"strategy_id": str(item), "ranking": rank}
    performance = _mapping(state.get("performance_panel"))
    return {
        "strategy_id": payload.get("strategy_id", payload.get("strategy", payload.get("name", f"strategy:{rank}"))),
        "status": payload.get("status", payload.get("recommendation", DATA_UNAVAILABLE)),
        "confidence": payload.get("confidence", payload.get("average_confidence", DATA_UNAVAILABLE)),
        "allocation": payload.get("allocation", payload.get("allocation_weight", DATA_UNAVAILABLE)),
        "risk": payload.get("risk", payload.get("risk_score", DATA_UNAVAILABLE)),
        "expectancy": payload.get("expectancy", performance.get("expectancy", DATA_UNAVAILABLE)),
        "capital_usage": payload.get("capital_usage", payload.get("allocated_capital", DATA_UNAVAILABLE)),
        "win_rate": payload.get("win_rate", performance.get("win_rate", DATA_UNAVAILABLE)),
        "profit_factor": payload.get("profit_factor", performance.get("profit_factor", DATA_UNAVAILABLE)),
        "sharpe": payload.get("sharpe", performance.get("sharpe", DATA_UNAVAILABLE)),
        "ranking": payload.get("ranking", payload.get("rank", rank)),
        **_metadata(state, "strategy_war_room.strategy"),
    }


def _institutional_source(state: Mapping[str, Any], key: str) -> dict[str, Any]:
    sources = _mapping(state.get("institutional_sources"))
    return _mapping(sources.get(key))


def _rows(source: Mapping[str, Any], *keys: str, fallback: Any = None) -> list[Any]:
    for key in keys:
        value = source.get(key)
        if isinstance(value, list):
            return value
    return fallback if isinstance(fallback, list) else []


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


__all__ = ["build_strategy_war_room"]
