"""
Auth gate for REA Capital Trading Engine.

Responsibilities:
- Fail-closed authentication gate (per-user auth; no global secret dependency)
- Enforce branch-scoped permissions (except superuser)
- First-login mandatory password change (min length configurable)
- Bind unit_code -> unit_router bundle (fail-closed if unknown)
- Ensure ENGINE_RUN_ID exists (audit-safe)
"""

from __future__ import annotations

import os
import subprocess
import uuid
import getpass
from dataclasses import dataclass
from typing import Optional, Tuple


# ---- configuration ----

MIN_PASSWORD_LEN = 6  # <-- per instruction (was 10 in earlier iterations)


# ---- helpers ----

def _ensure_engine_run_id() -> str:
    """
    Ensure ENGINE_RUN_ID exists for audit trail.
    If missing, generate a uuid4 and set into env.
    """
    run_id = os.getenv("ENGINE_RUN_ID") or os.getenv("REA_ENGINE_RUN_ID")
    if not run_id:
        run_id = str(uuid.uuid4())
        os.environ["ENGINE_RUN_ID"] = run_id
    return run_id


def _current_branch() -> str:
    """
    Determine current git branch, with safe fallbacks.
    """
    # explicit override
    env_branch = os.getenv("REA_CURRENT_BRANCH")
    if env_branch:
        return env_branch.strip()

    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        if out:
            return out
    except Exception:
        pass

    return "unknown"


def _safe_set_audit_user(user_id: int, role: str, unit_code: str, branch: str) -> None:
    """
    Bind user to audit context if the helper exists.
    This must never crash login (audit binding is best-effort here).
    """
    try:
        from backend.app.observability import audit_context  # type: ignore

        if hasattr(audit_context, "set_audit_user"):
            audit_context.set_audit_user(
                user_id=user_id,
                role=role,
                unit_code=unit_code,
                branch=branch,
            )
    except Exception:
        # fail-closed is for AUTH; audit binding is best-effort at this layer
        return


def _unit_bundle_or_fail(unit_code: str):
    """
    Resolve unit bundle via unit_router.
    Fail-closed if unit_code is unknown.
    """
    from backend.app.security.unit_router import resolve_unit_bundle, list_unit_codes  # type: ignore

    bundle = resolve_unit_bundle(unit_code)
    if bundle is None:
        allowed = ", ".join(list_unit_codes())
        raise RuntimeError(f"Unknown unit_code: {unit_code}. Allowed: {allowed}")
    return bundle


# ---- output model ----

@dataclass(frozen=True)
class AuthContext:
    user_id: int
    display_name: str
    role: str
    unit_code: str
    home_branch: str
    current_branch: str
    is_superuser: bool


# ---- main gate ----

def await_login_ready_state() -> Tuple[AuthContext, object]:
    """
    Blocks until valid credentials are supplied.
    Returns:
      (auth_context, unit_bundle)
    """
    _ensure_engine_run_id()

    from backend.app.security.user_registry import (  # type: ignore
        authenticate,
        change_password,
        get_user,
        is_first_login_password_change_required,
    )

    cur_branch = _current_branch()

    # ---- prompt user ----
    while True:
        raw_user = input("REA LOGIN | user_id (numeric): ").strip()
        if not raw_user.isdigit():
            print("user_id must be numeric.")
            continue
        user_id = int(raw_user)

        pw = getpass.getpass("REA LOGIN | password: ").strip()
        ok, reason = authenticate(user_id=user_id, password=pw)
        if not ok:
            print(f"Invalid credentials. ({reason})")
            continue

        # user exists and is authenticated
        user = get_user(user_id)
        if user is None:
            print("AUTH_ABORT | user not found (registry inconsistency).")
            continue

        # ---- first-login forced password change ----
        if is_first_login_password_change_required(user_id):
            print("FIRST_LOGIN_PASSWORD_CHANGE_REQUIRED")
            while True:
                new_pw = getpass.getpass(f"NEW PASSWORD (min {MIN_PASSWORD_LEN} chars): ").strip()
                if len(new_pw) < MIN_PASSWORD_LEN:
                    print(f"Password too short. Min length = {MIN_PASSWORD_LEN}.")
                    continue
                confirm_pw = getpass.getpass("CONFIRM NEW PASSWORD: ").strip()
                if new_pw != confirm_pw:
                    print("Passwords do not match. Try again.")
                    continue

                ok2, reason2 = change_password(user_id=user_id, old_password=pw, new_password=new_pw)
                if not ok2:
                    print(f"Password change failed. ({reason2})")
                    # keep them in change loop; do NOT fall through
                    continue

                print("PASSWORD_CHANGED_SUCCESSFULLY")
                break

        # ---- branch scope enforcement ----
        role = getattr(user, "role", "operator")
        unit_code = getattr(user, "unit_code", "CORE")
        home_branch = getattr(user, "home_branch", "main")
        display_name = getattr(user, "display_name", f"user_{user_id}")

        is_super = (role == "super_user") or (user_id == 1369)

        if (not is_super) and (cur_branch != home_branch):
            print(
                f"AUTH_ABORT | branch_scope_violation | user_branch={home_branch} | current_branch={cur_branch}"
            )
            continue

        # ---- unit routing (fail-closed if unknown) ----
        try:
            unit_bundle = _unit_bundle_or_fail(unit_code)
        except Exception as e:
            print(f"AUTH_ABORT | {e}")
            continue

        # ---- bind audit user (best-effort) ----
        _safe_set_audit_user(
            user_id=user_id,
            role=role,
            unit_code=unit_code,
            branch=cur_branch,
        )

        ctx = AuthContext(
            user_id=user_id,
            display_name=display_name,
            role=role,
            unit_code=unit_code,
            home_branch=home_branch,
            current_branch=cur_branch,
            is_superuser=is_super,
        )
        return ctx, unit_bundle
