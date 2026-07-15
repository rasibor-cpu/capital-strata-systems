from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dashboard.runtime.frontend_contract import DATA_UNAVAILABLE


ROLES = ("Administrator", "Operator", "Risk Officer", "Investment Officer", "Auditor", "Viewer")


def build_rbac_console(state: Mapping[str, Any]) -> dict[str, Any]:
    permissions = _mapping(state.get("permissions"))
    governance = _mapping(state.get("governance"))
    status = "fail_closed" if _runtime_unavailable(state) or not permissions else "available"
    return {
        "status": status,
        "current_role": governance.get("role", DATA_UNAVAILABLE),
        "roles": [_role_payload(role, permissions) for role in ROLES],
        "permissions": permissions,
        "role_editing": False,
        "write_routes_enabled": False,
        "operator_actions_enabled": False,
        "links": _links("users_governance", "audit_explainability", "system_configuration"),
        "read_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
        **_metadata(state, "rbac_console"),
    }


def _role_payload(role: str, permissions: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "role": role,
        "can_view": True,
        "can_change_state": False,
        "can_change_limits": False,
        "can_change_broker": False,
        "can_change_roles": False,
        "permission_source": permissions.get("rbac_source", "existing_css_rbac_display_only"),
    }


def _links(*keys: str) -> list[dict[str, str]]:
    return [{"label": key.replace("_", " ").title(), "route": f"/mission-control/{key.replace('_', '-')}"} for key in keys]


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


__all__ = ["ROLES", "build_rbac_console"]
