from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dashboard.runtime.frontend_contract import DATA_UNAVAILABLE


WORKFLOW_TYPES = ("configuration", "runtime", "broker", "capital", "strategy", "risk")


def build_approval_workflow_console(state: Mapping[str, Any]) -> dict[str, Any]:
    source = _mapping(_mapping(state.get("governance")).get("approval_workflows"))
    workflows = [_workflow(name, source.get(name)) for name in WORKFLOW_TYPES]
    return {
        "status": "fail_closed" if _runtime_unavailable(state) else "available",
        "workflows": workflows,
        "workflow_changes_enabled": False,
        "read_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
        **_metadata(state, "approval_workflow"),
    }


def _workflow(name: str, raw: Any) -> dict[str, Any]:
    payload = dict(raw) if isinstance(raw, Mapping) else {}
    return {
        "workflow": name,
        "chain": payload.get("chain", ["operator review", "risk review", "audit record"]),
        "approval_status": payload.get("approval_status", "not requested"),
        "required_roles": payload.get("required_roles", ["Operator", "Risk Officer", "Auditor"]),
        "changes_enabled": False,
        "read_only": True,
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


__all__ = ["WORKFLOW_TYPES", "build_approval_workflow_console"]
