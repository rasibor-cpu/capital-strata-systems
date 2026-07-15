from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dashboard.runtime.frontend_contract import DATA_UNAVAILABLE


def build_execution_committee_panel(state: Mapping[str, Any]) -> dict[str, Any]:
    trading = _mapping(state.get("trading"))
    lifecycle = _mapping(state.get("trade_lifecycle"))
    broker = _mapping(state.get("broker_telemetry"))
    attribution = _mapping(state.get("performance_attribution"))
    return {
        "status": "FAIL_CLOSED" if _runtime_unavailable(state) else trading.get("execution_quality", DATA_UNAVAILABLE),
        "execution_quality": trading.get("execution_quality", DATA_UNAVAILABLE),
        "latency": broker.get("latency", DATA_UNAVAILABLE),
        "slippage": trading.get("slippage", DATA_UNAVAILABLE),
        "fills": lifecycle.get("fills", []),
        "rejects": trading.get("rejections", []),
        "broker_quality": broker.get("connection_status", DATA_UNAVAILABLE),
        "routing_quality": attribution.get("execution_attribution", DATA_UNAVAILABLE),
        "controls": "READ_ONLY_DISABLED",
        "links": _links("trade_operations", "broker_management", "audit_explainability"),
        "read_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
        **_metadata(state, "execution_committee"),
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


__all__ = ["build_execution_committee_panel"]
