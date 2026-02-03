"""
backend/app/security/auth_gate.py

Startup authentication gate:
- Engine boots into READY state
- Blocks until user login is provided
- Returns an AuthContext containing user_id
- Fail-closed by default

Supports:
- Interactive login (stdin prompt)
- Non-interactive mode for automation via env variables
"""

from __future__ import annotations

import getpass
import os
import time
from dataclasses import dataclass
from typing import Optional

from backend.app.observability.logger import get_logger, with_trace
from backend.app.observability.kill_switch import assert_not_killed

log = get_logger("security.auth_gate")


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    auth_method: str  # "interactive" | "env"
    issued_at_utc: float


def _env_truthy(key: str) -> bool:
    v = os.getenv(key, "").strip().lower()
    return v in {"1", "true", "yes", "y", "on"}


def await_login_ready_state(timeout_s: int = 0) -> AuthContext:
    """
    Blocks until login is provided.

    If timeout_s == 0: wait indefinitely (recommended for deployed READY state).
    If timeout_s > 0: fail after timeout.

    Non-interactive override:
      REA_NONINTERACTIVE_USER_ID  -> user id
      REA_NONINTERACTIVE_AUTH_KEY -> shared key
      REA_EXPECTED_AUTH_KEY       -> expected key (or store elsewhere later)

    NOTE: For now we use a simple shared-key gate. Later we can swap to
    hashed passwords / TOTP / OS credential vault without changing callers.
    """
    adapter = with_trace(log, "LOGIN")

    # If kill-switch is active, block immediately.
    if not assert_not_killed(pair="GLOBAL"):
        adapter.critical("LOGIN_BLOCK | reason=kill_switch_active")
        raise RuntimeError("kill_switch_active")

    # Non-interactive mode (automation / service wrapper)
    non_user = os.getenv("REA_NONINTERACTIVE_USER_ID", "").strip()
    non_key = os.getenv("REA_NONINTERACTIVE_AUTH_KEY", "").strip()
    expected = os.getenv("REA_EXPECTED_AUTH_KEY", "").strip()

    if non_user and non_key and expected:
        if non_key == expected:
            adapter.info("LOGIN_OK | method=env | user_id=%s", non_user)
            return AuthContext(
                user_id=non_user,
                auth_method="env",
                issued_at_utc=time.time(),
            )
        adapter.critical("LOGIN_FAIL | method=env | user_id=%s | reason=bad_key", non_user)
        raise PermissionError("noninteractive_bad_key")

    # Interactive mode
    start = time.time()
    adapter.info("READY_STATE | awaiting_login=true")

    while True:
        if not assert_not_killed(pair="GLOBAL"):
            adapter.critical("LOGIN_ABORT | reason=kill_switch_active")
            raise RuntimeError("kill_switch_active")

        if timeout_s and (time.time() - start) > timeout_s:
            adapter.critical("LOGIN_TIMEOUT | timeout_s=%s", timeout_s)
            raise TimeoutError("login_timeout")

        try:
            user_id = input("REA LOGIN | user_id: ").strip()
            if not user_id:
                print("user_id is required.")
                continue

            pw = getpass.getpass("REA LOGIN | password/key (hidden): ").strip()
            if not pw:
                print("password/key is required.")
                continue

            # Minimal shared-key check:
            # - If REA_EXPECTED_AUTH_KEY is not set, fail-closed.
            # - If set, must match exactly.
            if not expected:
                adapter.critical("LOGIN_FAIL | method=interactive | reason=missing_expected_key_env")
                print("LOGIN BLOCKED: REA_EXPECTED_AUTH_KEY is not set on this machine.")
                print("Set REA_EXPECTED_AUTH_KEY, then retry.")
                continue

            if pw != expected:
                adapter.warning("LOGIN_FAIL | method=interactive | user_id=%s | reason=bad_key", user_id)
                print("Invalid credentials.")
                continue

            adapter.info("LOGIN_OK | method=interactive | user_id=%s", user_id)
            return AuthContext(
                user_id=user_id,
                auth_method="interactive",
                issued_at_utc=time.time(),
            )

        except KeyboardInterrupt:
            adapter.warning("LOGIN_ABORT | reason=ctrl_c")
            raise
        except Exception as e:
            adapter.error("LOGIN_ERROR | %s", str(e))
            print("Login error. Try again.")
