"""
backend/app/security/auth_gate.py

Startup authentication gate for REA Capital Trading Engine.

Responsibilities:
- Engine boots into READY state
- Blocks execution until valid login is completed
- Enforces kill-switch (fail-closed)
- Validates numeric user_id against registry
- Enforces branch-scoped permissions (except superuser)
- Binds authenticated AuditContext ONCE per engine run
"""

from __future__ import annotations

import getpass
import os
import time
from dataclasses import dataclass

from backend.app.observability.logger import get_logger, with_trace
from backend.app.observability.kill_switch import assert_not_killed
from backend.app.observability.engine_run import get_engine_run_id
from backend.app.observability.audit_context import (
    set_audit_context,
    AuditContext,
)
from backend.app.security.user_registry import (
    ensure_superuser_exists,
    get_user,
    get_current_branch,
    branch_allowed,
    SUPERUSER_ID,
)

log = get_logger("security.auth_gate")


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    role: str
    home_branch: str
    current_branch: str
    auth_method: str
    issued_at_utc: float


def await_login_ready_state(timeout_s: int = 0) -> AuthContext:
    """
    Blocks until a valid login is completed.

    Environment (non-interactive) mode:
      REA_NONINTERACTIVE_USER_ID
      REA_NONINTERACTIVE_AUTH_KEY
      REA_EXPECTED_AUTH_KEY   (required)

    Interactive mode:
      Prompts user_id + key securely
    """
    adapter = with_trace(log, "LOGIN")

    ensure_superuser_exists()

    if not assert_not_killed(pair="GLOBAL"):
        adapter.critical("LOGIN_BLOCK | reason=kill_switch_active")
        raise RuntimeError("kill_switch_active")

    expected_key = os.getenv("REA_EXPECTED_AUTH_KEY", "").strip()
    if not expected_key:
        adapter.critical("LOGIN_BLOCK | reason=missing_REA_EXPECTED_AUTH_KEY")
        raise RuntimeError("REA_EXPECTED_AUTH_KEY not set (fail-closed)")

    current_branch = get_current_branch()
    engine_run_id = get_engine_run_id()

    # -------------------------
    # Non-interactive login
    # -------------------------
    env_user = os.getenv("REA_NONINTERACTIVE_USER_ID", "").strip()
    env_key = os.getenv("REA_NONINTERACTIVE_AUTH_KEY", "").strip()

    if env_user and env_key:
        if env_key != expected_key:
            adapter.critical("LOGIN_FAIL | method=env | user_id=%s | reason=bad_key", env_user)
            raise PermissionError("invalid_credentials")

        rec = get_user(env_user)
        if rec is None:
            adapter.critical("LOGIN_FAIL | method=env | user_id=%s | reason=unknown_user", env_user)
            raise PermissionError("unknown_user")

        if not branch_allowed(rec, current_branch):
            adapter.critical(
                "LOGIN_FAIL | method=env | user_id=%s | reason=branch_restricted | home=%s | current=%s",
                rec.user_id, rec.home_branch, current_branch
            )
            raise PermissionError("branch_restricted")

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

        adapter.info(
            "LOGIN_OK | method=env | user_id=%s | role=%s | branch=%s",
            rec.user_id, rec.role, current_branch
        )

        return AuthContext(
            user_id=rec.user_id,
            role=rec.role,
            home_branch=rec.home_branch,
            current_branch=current_branch,
            auth_method="env",
            issued_at_utc=time.time(),
        )

    # -------------------------
    # Interactive login
    # -------------------------
    adapter.info("READY_STATE | awaiting_login=true | branch=%s", current_branch)
    start = time.time()

    while True:
        if not assert_not_killed(pair="GLOBAL"):
            adapter.critical("LOGIN_ABORT | reason=kill_switch_active")
            raise RuntimeError("kill_switch_active")

        if timeout_s and (time.time() - start) > timeout_s:
            adapter.critical("LOGIN_TIMEOUT | timeout_s=%s", timeout_s)
            raise TimeoutError("login_timeout")

        try:
            user_id = input("REA LOGIN | user_id (numeric): ").strip()
            if not user_id.isdigit():
                print("user_id must be numeric.")
                continue

            key = getpass.getpass("REA LOGIN | password/key: ").strip()
            if key != expected_key:
                adapter.warning(
                    "LOGIN_FAIL | method=interactive | user_id=%s | reason=bad_key",
                    user_id,
                )
                print("Invalid credentials.")
                continue

            rec = get_user(user_id)
            if rec is None:
                adapter.warning(
                    "LOGIN_FAIL | method=interactive | user_id=%s | reason=unknown_user",
                    user_id,
                )
                print("Unknown user_id.")
                continue

            if not branch_allowed(rec, current_branch):
                adapter.critical(
                    "LOGIN_FAIL | method=interactive | user_id=%s | reason=branch_restricted | home=%s | current=%s",
                    rec.user_id, rec.home_branch, current_branch
                )
                print(f"Access denied: restricted to branch '{rec.home_branch}'.")
                continue

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

            adapter.info(
                "LOGIN_OK | method=interactive | user_id=%s | role=%s | branch=%s",
                rec.user_id, rec.role, current_branch
            )

            return AuthContext(
                user_id=rec.user_id,
                role=rec.role,
                home_branch=rec.home_branch,
                current_branch=current_branch,
                auth_method="interactive",
                issued_at_utc=time.time(),
            )

        except KeyboardInterrupt:
            adapter.warning("LOGIN_ABORT | reason=ctrl_c")
            raise
        except Exception as exc:
            adapter.error("LOGIN_ERROR | %s", str(exc))
            print("Login error. Try again.")

