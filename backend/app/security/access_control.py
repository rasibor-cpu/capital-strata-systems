"""
backend/app/security/access_control.py

Hard enforcement of module-level permissions derived from the authenticated user.

Flow:
- auth_gate returns AuthContext(modules=...)
- engine / api / cli actions must call require_module("module.name")
- SUPER user uses modules=["*"] which allows all.

Fail-closed:
- If audit context not initialized or auth context missing -> block.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Set

from backend.app.observability.logger import get_logger, with_trace
from backend.app.observability.audit_context import get_audit_context

log = get_logger("security.access_control")


@dataclass(frozen=True)
class Permissions:
    user_id: str
    role: str
    modules: Set[str]


_PERMS: Optional[Permissions] = None


def set_permissions(user_id: str, role: str, modules: Iterable[str]) -> None:
    """
    Called once after successful login.
    """
    global _PERMS
    _PERMS = Permissions(user_id=user_id, role=role, modules=set(modules))


def get_permissions() -> Permissions:
    if _PERMS is None:
        raise RuntimeError("PERMISSIONS_NOT_INITIALIZED")
    return _PERMS


def is_allowed(module: str) -> bool:
    p = get_permissions()
    if "*" in p.modules:
        return True
    return module in p.modules


def require_module(module: str) -> None:
    """
    Enforcement gate. Call this at the start of every action/screen/function.
    """
    adapter = with_trace(log, "ACCESS")

    # Ensure we have an authenticated audit context (fail-closed)
    _ = get_audit_context()

    if not is_allowed(module):
        p = get_permissions()
        adapter.critical(
            "ACCESS_DENIED | user_id=%s | role=%s | module=%s",
            p.user_id, p.role, module
        )
        raise PermissionError(f"ACCESS_DENIED:{module}")

    adapter.info("ACCESS_OK | module=%s", module)
