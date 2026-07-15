from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dashboard.runtime.frontend_contract import DATA_UNAVAILABLE


FLAG_STATES = ("enabled", "disabled", "pending", "deprecated", "experimental")


def build_feature_flags_console(state: Mapping[str, Any]) -> dict[str, Any]:
    config = _mapping(state.get("configuration"))
    raw_flags = _mapping(config.get("feature_flags"))
    flags = _flags(raw_flags)
    return {
        "status": "fail_closed" if _runtime_unavailable(state) else "available",
        "flags": flags,
        "summary": {name: len([flag for flag in flags if flag["state"] == name]) for name in FLAG_STATES},
        "editing_enabled": False,
        "read_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
        **_metadata(state, "feature_flags"),
    }


def _flags(raw_flags: Mapping[str, Any]) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    for name in sorted(raw_flags):
        value = raw_flags[name]
        if isinstance(value, Mapping):
            state = str(value.get("state", "disabled")).lower()
            description = value.get("description", DATA_UNAVAILABLE)
        else:
            state = "enabled" if value is True else "disabled"
            description = DATA_UNAVAILABLE
        if state not in FLAG_STATES:
            state = "pending"
        flags.append({"flag": str(name), "state": state, "description": description})
    return flags


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


__all__ = ["FLAG_STATES", "build_feature_flags_console"]
