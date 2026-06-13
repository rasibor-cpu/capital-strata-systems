"""
backend/app/security/live_toggle.py

Hard gate between TEST and LIVE execution.

Default:
- Engine runs in TEST mode.
- LIVE must be explicitly authorized by RBAC/permission controls.

Fail-closed:
- Missing context, missing role, or ambiguity blocks LIVE execution.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Mapping

from backend.app.observability.audit_context import require_audit_user
from backend.app.observability.logger import get_logger, with_trace

log = get_logger("security.live_toggle")

LIVE_AUTHORIZED_ROLES = {"SUPER_USER"}
LIVE_PERMISSION_KEYS = {"can_execute_live_trading"}


@dataclass(frozen=True)
class LiveToggleContext:
    user_id: str
    role: str
    permissions: Mapping[str, Any]


def get_engine_mode() -> str:
    return os.getenv("REA_ENGINE_MODE", "TEST").upper().strip()


def is_live_mode() -> bool:
    return get_engine_mode() == "LIVE"


def _normalize_role(role: Any) -> str:
    return str(role or "").strip().upper().replace(" ", "_").replace("-", "_")


def _mapping_get(source: Any, key: str, default: Any = None) -> Any:
    if isinstance(source, Mapping):
        return source.get(key, default)
    return getattr(source, key, default)


def _context_from_audit_user() -> LiveToggleContext:
    user = require_audit_user()
    return LiveToggleContext(
        user_id=str(user.user_id),
        role=_normalize_role(user.role),
        permissions={},
    )


def _context_from_mapping(user_context: Mapping[str, Any]) -> LiveToggleContext:
    role_profile = _mapping_get(user_context, "role_profile", {}) or {}
    permissions = _mapping_get(user_context, "permissions", {}) or {}

    merged_permissions: dict[str, Any] = {}
    if isinstance(permissions, Mapping):
        merged_permissions.update(permissions)
    if isinstance(role_profile, Mapping):
        merged_permissions.update(role_profile)

    for key in LIVE_PERMISSION_KEYS:
        if key in user_context:
            merged_permissions[key] = user_context[key]

    return LiveToggleContext(
        user_id=str(_mapping_get(user_context, "user_id", "")),
        role=_normalize_role(_mapping_get(user_context, "role", "")),
        permissions=merged_permissions,
    )


def _resolve_live_toggle_context(
    user_context: Mapping[str, Any] | None = None,
) -> LiveToggleContext:
    if user_context is not None:
        return _context_from_mapping(user_context)
    return _context_from_audit_user()


def is_live_execution_authorized(
    user_context: Mapping[str, Any] | None = None,
) -> tuple[bool, str, LiveToggleContext | None]:
    try:
        ctx = _resolve_live_toggle_context(user_context)
    except Exception:
        return False, "live_toggle_context_missing", None

    if not ctx.role:
        return False, "live_toggle_role_missing", ctx

    if ctx.role in LIVE_AUTHORIZED_ROLES:
        return True, "live_toggle_super_user_role_authorized", ctx

    for key in LIVE_PERMISSION_KEYS:
        if ctx.permissions.get(key) is True:
            return True, f"live_toggle_permission_authorized:{key}", ctx

    return False, "live_toggle_rbac_denied", ctx


def require_live_allowed(
    user_context: Mapping[str, Any] | None = None,
) -> None:
    """
    Call immediately before any REAL execution.

    This authorizes the live-toggle boundary only. It does not place orders,
    set broker environment flags, or bypass broker firewalls.
    """
    adapter = with_trace(log, "LIVE")

    if not is_live_mode():
        adapter.info("EXECUTION_BLOCKED | mode=TEST")
        raise RuntimeError("EXECUTION_BLOCKED_TEST_MODE")

    allowed, reason, ctx = is_live_execution_authorized(user_context)
    user_id = ctx.user_id if ctx else "N/A"
    role = ctx.role if ctx else "N/A"

    if not allowed:
        adapter.critical(
            "LIVE_DENIED | user_id=%s | role=%s | reason=%s",
            user_id,
            role,
            reason,
        )
        raise PermissionError("LIVE_EXECUTION_DENIED")

    adapter.critical(
        "LIVE_EXECUTION_ARMED | user_id=%s | role=%s | reason=%s | at_utc=%s",
        user_id,
        role,
        reason,
        time.time(),
    )
