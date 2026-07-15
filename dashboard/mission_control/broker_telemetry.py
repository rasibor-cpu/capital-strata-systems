from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dashboard.runtime.frontend_contract import DATA_UNAVAILABLE


def build_broker_telemetry(state: Mapping[str, Any]) -> dict[str, Any]:
    brokers = _mapping(state.get("brokers"))
    active = _mapping(brokers.get("active_broker"))
    runtime = _mapping(state.get("runtime"))
    return {
        "broker": active.get("selected_broker", DATA_UNAVAILABLE),
        "authentication": active.get("authentication_status", DATA_UNAVAILABLE),
        "connection": active.get("connection_status", DATA_UNAVAILABLE),
        "transport": active.get("connection_status", DATA_UNAVAILABLE),
        "latency": active.get("latency", DATA_UNAVAILABLE),
        "market_data_freshness": active.get("freshness", DATA_UNAVAILABLE),
        "heartbeat": runtime.get("heartbeat", DATA_UNAVAILABLE),
        "api_availability": runtime.get("subsystem_health", {}).get("api", DATA_UNAVAILABLE) if isinstance(runtime.get("subsystem_health"), Mapping) else DATA_UNAVAILABLE,
        "rate_limits": DATA_UNAVAILABLE,
        "products": active.get("capabilities", []),
        "account_readiness": active.get("account_status", DATA_UNAVAILABLE),
        "warnings": active.get("warnings", []),
        "overall_health": active.get("broker_health", active.get("connection_status", DATA_UNAVAILABLE)),
        "read_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
        **_metadata(state, "broker_telemetry"),
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


__all__ = ["build_broker_telemetry"]
