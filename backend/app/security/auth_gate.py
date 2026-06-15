"""
Authoritative authentication gate for REA Capital Trading Engine.

Design goals:
- NEVER crash on import (wrapper must be able to import this module)
- Work with user_registry even if its function names change
- Enforce "password length at most 6"
- Allow deterministic initial password: 123456
- Return a user_ctx dict on success
"""

from __future__ import annotations

from dataclasses import dataclass
from getpass import getpass
import importlib
from typing import Any, Dict, Optional


INITIAL_PASSWORD = "123456"
MAX_PASSWORD_LEN = 6


def _safe_import_user_registry():
    """
    Import user_registry without breaking the entire program.
    If this fails, auth gate still loads, but login will fail-closed.
    """
    try:
        return importlib.import_module("backend.app.security.user_registry")
    except Exception:
        return None


def _coerce_user_record(raw: Any) -> Optional[Dict[str, Any]]:
    """
    Normalize whatever user_registry returns into a dict-like record.
    Accepts dict or objects with __dict__.
    """
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    # dataclass / object fallback
    d = getattr(raw, "__dict__", None)
    if isinstance(d, dict):
        return d
    return None


def _get_user_any(ur_mod, user_id: int) -> Optional[Dict[str, Any]]:
    """
    Try multiple APIs to fetch a user record.
    """
    if ur_mod is None:
        return None

    # 1) get_user(user_id)
    fn = getattr(ur_mod, "get_user", None)
    if callable(fn):
        try:
            return _coerce_user_record(fn(user_id))
        except Exception:
            return None

    # 2) find_user(user_id)
    fn = getattr(ur_mod, "find_user", None)
    if callable(fn):
        try:
            return _coerce_user_record(fn(user_id))
        except Exception:
            return None

    # 3) load_users() -> dict or list
    fn = getattr(ur_mod, "load_users", None)
    if callable(fn):
        try:
            users = fn()
            if isinstance(users, dict):
                # could be keyed by str/int
                return _coerce_user_record(users.get(user_id) or users.get(str(user_id)))
            if isinstance(users, list):
                for u in users:
                    ud = _coerce_user_record(u)
                    if ud and str(ud.get("user_id")) == str(user_id):
                        return ud
        except Exception:
            return None

    return None


def _verify_password_any(ur_mod, user: Dict[str, Any], password: str) -> bool:
    """
    Try multiple APIs to verify password.
    Must return boolean.
    """
    if ur_mod is None:
        return False

    # 1) authenticate(user_id, password) -> bool
    fn = getattr(ur_mod, "authenticate", None)
    if callable(fn):
        try:
            out = fn(int(user.get("user_id")), password)
            return bool(out is True or _coerce_user_record(out) is not None)
        except Exception:
            return False

    # 2) verify_password(user, password) -> bool
    fn = getattr(ur_mod, "verify_password", None)
    if callable(fn):
        try:
            out = fn(user, password)
            return bool(out is True)
        except Exception:
            return False

    # 3) ultra-fallback (only if registry stores plaintext fields)
    #    We keep this LAST and conservative.
    stored = user.get("password") or user.get("temp_password")
    if isinstance(stored, str) and stored == password:
        return True

    return False


def _change_password_any(ur_mod, user_id: int, new_pw: str) -> bool:
    """
    Best-effort password change, branch-scoped per registry rules.
    """
    if ur_mod is None:
        return False

    fn = getattr(ur_mod, "change_password", None)
    if callable(fn):
        try:
            out = fn(user_id, new_pw)
            return bool(out is True)
        except Exception:
            return False

    fn = getattr(ur_mod, "set_password", None)
    if callable(fn):
        try:
            out = fn(user_id, new_pw)
            return bool(out is True)
        except Exception:
            return False

    return False


def _prompt_new_password() -> str:
    """
    Enforce <= 6 characters. (User requirement: 'at most 6')
    """
    while True:
        new_pw = getpass(f"NEW PASSWORD (max {MAX_PASSWORD_LEN} chars): ").strip()
        if not new_pw:
            print("Password cannot be empty.")
            continue
        if len(new_pw) > MAX_PASSWORD_LEN:
            print(f"Password too long. Max is {MAX_PASSWORD_LEN}.")
            continue

        confirm = getpass("CONFIRM NEW PASSWORD: ").strip()
        if new_pw != confirm:
            print("Passwords do not match.")
            continue
        return new_pw


def await_login_ready_state() -> Dict[str, Any]:
    """
    Blocking login gate.
    Returns: user_ctx dict (used to drive routing & audit).
    Fail-closed by raising RuntimeError.
    """

    ur = _safe_import_user_registry()
    if ur is None:
        raise RuntimeError("AUTH_REGISTRY_IMPORT_FAILED")

    raw = input("REA LOGIN | user_id (numeric): ").strip()
    try:
        user_id = int(raw)
    except Exception:
        raise RuntimeError("INVALID_USER_ID")

    user = _get_user_any(ur, user_id)
    if not user:
        raise RuntimeError("AUTH_FAILED")

    pw = getpass("REA LOGIN | password: ").strip()

    # Enforce <= 6
    if len(pw) > MAX_PASSWORD_LEN:
        raise RuntimeError("AUTH_FAILED")

    # Deterministic initial password (first access)
    if pw == INITIAL_PASSWORD:
        # Require change on first use (always)
        print("FIRST_LOGIN_PASSWORD_CHANGE_REQUIRED")
        new_pw = _prompt_new_password()
        changed = _change_password_any(ur, user_id, new_pw)
        if changed is not True:
            raise RuntimeError("PASSWORD_CHANGE_FAILED")

        # reload user (in case registry updates flags/fields)
        user = _get_user_any(ur, user_id) or user

    else:
        ok = _verify_password_any(ur, user, pw)
        if ok is not True:
            raise RuntimeError("AUTH_FAILED")

        # If registry marks first login required, enforce change if field exists
        must_change = user.get("must_change_password") or user.get("first_login_change_required")
        if must_change:
            print("FIRST_LOGIN_PASSWORD_CHANGE_REQUIRED")
            new_pw = _prompt_new_password()
            changed = _change_password_any(ur, user_id, new_pw)
            if changed is not True:
                raise RuntimeError("PASSWORD_CHANGE_FAILED")
            user = _get_user_any(ur, user_id) or user

    # Build user context (keys your engine expects)
    return {
        "user_id": int(user.get("user_id", user_id)),
        "display_name": str(user.get("display_name", "Unknown")),
        "role": str(user.get("role", "operator")),
        "unit_code": str(user.get("unit_code", "CORE")),
        "home_branch": str(user.get("home_branch", "main")),
    }
