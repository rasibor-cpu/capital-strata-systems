"""
backend/app/security/auth_gate.py

Login gate for REA Capital Trading Engine.

Key point:
- DO NOT import backend.app.observability.engine_run (it does not exist in this repo)
- ENGINE_RUN_ID is sourced from env or generated here.

This gate:
- Fail-closed on kill-switch
- Blocks until valid login
- Enforces branch scoping (except superuser)
- Resolves unit_code -> module bundle
- Binds AuditContext + Permissions
"""

from __future__ import annotations

import getpass
import os
import time
import uuid
from dataclasses import dataclass
from typing import List

from backend.app.observability.logger import get_logger, with_trace
from backend.app.observability.kill_switch import assert_not_killed
from backend.app.observability.audit_context import AuditContext, set_audit_context

from backend.app.security.user_registry import (
    ensure_superuser_exists,
    get_user,
    get_current_branch,
    branch_allowed,
)
from backend.app.security.unit_router import resolve_unit_bundle, UnitBundle
from backend.app.security.access_control import set_permissions

log = get_logger("security.auth_gate")


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    role: str
    unit_code: str
    unit_label: str
    modules: List[str]
    home_branch: str
    current_branch: str
    auth_method: str
    issued_at_utc: float


def _ensure_engine_run_id() -> str:
    rid = os.getenv("ENGINE_RUN_ID", "").strip()
    if not rid:
        rid = str(uuid.uuid4())
        os.environ["ENGINE_RUN_ID"] = rid
    return rid


def await_login_ready_state(timeout_s: int = 0) -> AuthContext:
    adapter = with_trace(log, "LOGIN")

    ensure_superuser_exists()

    # Fail-closed kill switch
    if not assert_not_killed(pair="GLOBAL"):
        adapter.critical("LOGIN_BLOCK | reason=kill_switch_active")
        raise RuntimeError("kill_switch_active")

    expected_key = os.getenv("REA_EXPECTED_AUTH_KEY", "").strip()
    if not expected_key:
        adapter.critical("LOGIN_BLOCK | reason=missing_REA_EXPECTED_AUTH_KEY")
        raise RuntimeError("REA_EXPECTED_AUTH_KEY not set (fail-closed)")

    current_branch = get_current_branch()
    engine_run_id = _ensure_engine_run_id()

    adapter.info("READY_STATE | awaiting_login=true | branch=%s", current_branch)

    start = time.time()

    while True:
        if not assert_not_killed(pair="GLOBAL"):
            adapter.critical("LOGIN_ABORT | reason=kill_switch_active")
            raise RuntimeError("kill_switch_active")

        if timeout_s and (time.time() - start) > timeout_s:
            adapter.critical("LOGIN_TIMEOUT | timeout_s=%s", timeout_s)
            raise TimeoutError("login_timeout")

        user_id = input("REA LOGIN | user_id (numeric): ").strip()
        if not user_id.isdigit():
            print("user_id must be numeric.")
            continue

        key = getpass.getpass("REA LOGIN | password/key: ").strip()
        if key != expected_key:
            adapter.warning("LOGIN_FAIL | user_id=%s | reason=bad_key", user_id)
            print("Invalid credentials.")
            continue

        rec = get_user(user_id)
        if rec is None:
            adapter.warning("LOGIN_FAIL | user_id=%s | reason=unknown_user", user_id)
            print("Unknown user_id.")
            continue

        if not branch_allowed(rec, current_branch):
            adapter.critical(
                "LOGIN_FAIL | user_id=%s | reason=branch_restricted | home=%s | current=%s",
                rec.user_id,
                rec.home_branch,
                current_branch,
            )
            print(f"Access denied: restricted to branch '{rec.home_branch}'.")
            continue

        # Unit -> module bundle
        if rec.role.lower() == "superuser":
            bundle = UnitBundle(unit_code="SUPER", label="Super User", modules=["*"])
        else:
            bundle = resolve_unit_bundle(rec.unit_code)

        # Bind audit context
        set_audit_context(
            AuditContext(
                user_id=rec.user_id,
                role=rec.role,
                home_branch=rec.home_branch,
                current_branch=current_branch,
                engine_run_id=engine_run_id,
                issued_at_utc=time.time(),
            )
        )

        # Bind permissions allowlist
        set_permissions(user_id=rec.user_id, role=rec.role, modules=bundle.modules)

        adapter.info(
            "LOGIN_OK | user_id=%s | role=%s | unit=%s | branch=%s",
            rec.user_id,
            rec.role,
            bundle.unit_code,
            current_branch,
        )

        return AuthContext(
            user_id=rec.user_id,
            role=rec.role,
            unit_code=bundle.unit_code,
            unit_label=bundle.label,
            modules=bundle.modules,
            home_branch=rec.home_branch,
            current_branch=current_branch,
            auth_method="interactive",
            issued_at_utc=time.time(),
        )
