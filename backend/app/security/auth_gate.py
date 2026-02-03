"""
backend/app/security/auth_gate.py

Startup authentication gate:
- Engine boots into READY state
- Blocks until user login is provided
- Validates user_id exists in registry
- Enforces branch restriction for non-super users
- Returns AuthContext containing user_id + role + home_branch

Fail-closed by default.
"""

from __future__ import annotations

import getpass
import os
import time
from dataclasses import dataclass

from backend.app.observability.logger import get_logger, with_trace
from backend.app.observability.kill_switch import assert_not_killed
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
    auth_method: str  # "interactive" | "env"
    issued_at_utc: float


def await_login_ready_state(timeout_s: int = 0) -> AuthContext:
    """
    Blocks until login is provided and validated.

    Non-interactive override:
      REA_NONINTERACTIVE_USER_ID  -> numeric user id
      REA_NONINTERACTIVE_AUTH_KEY -> shared key
      REA_EXPECTED_AUTH_KEY       -> expected key (required; fail-closed if missing)
    """
    adapter = with_trace(log, "LOGIN")

    # Ensure superuser exists (1369)
    ensure_superuser_exists()

    if not assert_not_killed(pair="GLOBAL"):
        adapter.critical("LOGIN_BLOCK | reason=kill_switch_active")
        raise RuntimeError("kill_switch_active")

    expected = os.getenv("REA_EXPECTED_AUTH_KEY", "").strip()
    if not expected:
        adapter.critical("LOGIN_BLOCK | reason=missing_REA_EXPECTED_AUTH_KEY")
        raise RuntimeError("REA_EXPECTED_AUTH_KEY is not set (fail-closed)")

    current_branch = get_current_branch()

    # Non-interactive mode
    non_user = os.getenv("REA_NONINTERACTIVE_USER_ID", "").strip()
    non_key = os.getenv("REA_NONINTERACTIVE_AUTH_KEY", "").strip()

    if non_user and non_key:
        if non_key != expected:
            adapter.critical("LOGIN_FAIL | method=env | user_id=%s | reason=bad_key", non_user)
            raise PermissionError("bad_key")

        rec = get_user(non_user)
        if rec is None:
            adapter.critical("LOGIN_FAIL | method=env | user_id=%s | reason=unknown_user", non_user)
            raise PermissionError("unknown_user")

        if not branch_allowed(rec, current_branch):
            adapter.critical(
                "LOGIN_FAIL | method=env | user_id=%s | reason=branch_restricted | home=%s | current=%s",
                rec.user_id, rec.home_branch, current_branch
            )
            raise PermissionError("branch_restricted")

        adapter.info("LOGIN_OK | method=env | user_id=%s | role=%s | branch=%s", rec.user_id, rec.role, current_branch)
        return AuthContext(
            user_id=rec.user_id,
            role=rec.role,
            home_branch=rec.home_branch,
            current_branch=current_branch,
            auth_method="env",
            issued_at_utc=time.time(),
        )

    # Interactive mode
    start = time.time()
    adapter.info("READY_STATE | awaiting_login=true | branch=%s", current_branch)

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

            pw = getpass.getpass("REA LOGIN | password/key (hidden): ").strip()
            if pw != expected:
                adapter.warning("LOGIN_FAIL | method=interactive | user_id=%s | reason=bad_key", user_id)
                print("Invalid credentials.")
                continue

            rec = get_user(user_id)
            if rec is None:
                adapter.warning("LOGIN_FAIL | method=interactive | user_id=%s | reason=unknown_user", user_id)
                print("Unknown user_id. Create the user first in runtime/users.json.")
                continue

            if not branch_allowed(rec, current_branch):
                adapter.critical(
                    "LOGIN_FAIL | method=interactive | user_id=%s | reason=branch_restricted | home=%s | current=%s",
                    rec.user_id, rec.home_branch, current_branch
                )
                print(f"Access denied: user is restricted to branch '{rec.home_branch}'.")
                continue

            adapter.info("LOGIN_OK | method=interactive | user_id=%s | role=%s | branch=%s", rec.user_id, rec.role, current_branch)
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
        except Exception as e:
            adapter.error("LOGIN_ERROR | %s", str(e))
            print("Login error. Try again.")
