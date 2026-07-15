from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dashboard.runtime.frontend_contract import DATA_UNAVAILABLE


def build_broker_registry_console(state: Mapping[str, Any]) -> dict[str, Any]:
    brokers = _mapping(state.get("brokers"))
    active = _mapping(brokers.get("active_broker"))
    registered = brokers.get("broker_list") if isinstance(brokers.get("broker_list"), list) else []
    return {
        "status": "fail_closed" if _runtime_unavailable(state) else active.get("connection_status", DATA_UNAVAILABLE),
        "registered_brokers": registered,
        "active_broker": active.get("selected_broker", DATA_UNAVAILABLE),
        "broker_environment_profile": active.get("broker_environment_profile", {}),
        "capabilities": active.get("capabilities", []),
        "certification": _mapping(state.get("certification")).get("broker_readiness", DATA_UNAVAILABLE),
        "readiness": active.get("account_status", DATA_UNAVAILABLE),
        "broker_status": active.get("connection_status", DATA_UNAVAILABLE),
        "supported_products": active.get("supported_asset_classes", []),
        "editing_enabled": False,
        "protected_fields_redacted": True,
        "read_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
        **_metadata(state, "broker_registry"),
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
        "runtime_id": runtime.get("runtime_id", snapshot.get("runtime_id", DATA_UNAVAILABLE)),
        "state_hash": runtime.get("state_hash", snapshot.get("state_hash", DATA_UNAVAILABLE)),
    }


def _runtime_unavailable(state: Mapping[str, Any]) -> bool:
    runtime = _mapping(state.get("runtime"))
    return str(runtime.get("runtime_status", "")).upper() in {"OFFLINE", "UNAVAILABLE"} or str(runtime.get("source", "")).upper() in {"", "UNAVAILABLE", "UNKNOWN"}


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


__all__ = ["build_broker_registry_console"]
