from __future__ import annotations

from collections.abc import Mapping
from typing import Any


READ_ONLY_PERMISSIONS = {
    "read_only": True,
    "can_execute": False,
    "can_arm_broker": False,
    "can_modify_limits": False,
    "can_modify_credentials": False,
    "can_restart_runtime": False,
    "can_shutdown_runtime": False,
    "can_change_broker": False,
}


def mission_control_permissions_payload(source: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {
        **READ_ONLY_PERMISSIONS,
        "source": "dashboard.mission_control.permissions",
        "rbac_source": "existing_css_rbac_display_only",
        "write_routes_enabled": False,
        "operator_actions_enabled": False,
    }


def validate_read_only_permissions(payload: Mapping[str, Any] | None) -> tuple[bool, list[str]]:
    permissions = payload if isinstance(payload, Mapping) else {}
    reasons: list[str] = []
    for key, expected in READ_ONLY_PERMISSIONS.items():
        if permissions.get(key) is not expected:
            reasons.append(f"permission_invalid:{key}")
    if permissions.get("write_routes_enabled") is not False:
        reasons.append("permission_invalid:write_routes_enabled")
    if permissions.get("operator_actions_enabled") is not False:
        reasons.append("permission_invalid:operator_actions_enabled")
    return not reasons, sorted(set(reasons))


__all__ = [
    "READ_ONLY_PERMISSIONS",
    "mission_control_permissions_payload",
    "validate_read_only_permissions",
]
