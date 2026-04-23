"""
Authoritative authentication gate for REA Capital Trading Engine.

Design goals:
- NEVER crash on import (wrapper must be able to import this module)
- Work with user_registry even if its function names change
- Enforce "password length at most 6"
- Allow deterministic initial password: 123456
- Preserve zero-padded 5-digit user IDs (e.g. 00000 stays 00000)
- Return a user_ctx dict on success
"""

from __future__ import annotations

from getpass import getpass
import importlib
import sys
from typing import Any, Dict, Optional


INITIAL_PASSWORD = "123456"
MAX_PASSWORD_LEN = 6
USER_ID_LEN = 5


def _safe_import_user_registry():
    """
    Import user_registry without breaking the entire program.
    If this fails, auth gate still loads, but login will fail-closed.
    """
    try:
        return importlib.import_module("backend.app.security.user_registry")
    except Exception:
        return None


def _normalize_user_id(raw: Any) -> str:
    """
    Preserve user IDs as zero-padded 5-digit strings.
    Accepts numeric-like input only.
    """
    user_id = str(raw).strip()

    if not user_id.isdigit():
        raise RuntimeError("INVALID_USER_ID")

    if len(user_id) > USER_ID_LEN:
        raise RuntimeError("INVALID_USER_ID")

    return user_id.zfill(USER_ID_LEN)


def _coerce_user_record(raw: Any) -> Optional[Dict[str, Any]]:
    """
    Normalize whatever user_registry returns into a dict-like record.
    Accepts dict or objects with __dict__.
    """
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    d = getattr(raw, "__dict__", None)
    if isinstance(d, dict):
        return d
    return None


def _get_user_any(ur_mod, user_id: str) -> Optional[Dict[str, Any]]:
    """
    Try multiple APIs to fetch a user record.
    """
    if ur_mod is None:
        return None

    fn = getattr(ur_mod, "get_user", None)
    if callable(fn):
        try:
            return _coerce_user_record(fn(user_id))
        except Exception:
            return None

    fn = getattr(ur_mod, "find_user", None)
    if callable(fn):
        try:
            return _coerce_user_record(fn(user_id))
        except Exception:
            return None

    fn = getattr(ur_mod, "load_users", None)
    if callable(fn):
        try:
            users = fn()
            if isinstance(users, dict):
                return _coerce_user_record(
                    users.get(user_id)
                    or users.get(str(user_id))
                    or users.get(int(user_id))
                )
            if isinstance(users, list):
                for u in users:
                    ud = _coerce_user_record(u)
                    if ud and _normalize_user_id(ud.get("user_id")) == user_id:
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

    fn = getattr(ur_mod, "authenticate", None)
    if callable(fn):
        try:
            out = fn(_normalize_user_id(user.get("user_id")), password)
            return bool(out is True)
        except Exception:
            return False

    fn = getattr(ur_mod, "verify_password", None)
    if callable(fn):
        try:
            out = fn(user, password)
            return bool(out is True)
        except Exception:
            return False

    stored = user.get("password") or user.get("temp_password")
    if isinstance(stored, str) and stored == password:
        return True

    return False


def _change_password_any(ur_mod, user_id: str, new_pw: str) -> bool:
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


def _prompt_masked_password(prompt: str, max_len: int) -> str:
    """
    Prompt for password while displaying one '#' per typed character.
    Supports backspace on Windows consoles.
    Falls back safely to getpass on unsupported environments.
    """
    try:
        import msvcrt

        sys.stdout.write(prompt)
        sys.stdout.flush()

        chars: list[str] = []

        while True:
            ch = msvcrt.getwch()

            if ch in ("\r", "\n"):
                sys.stdout.write("\n")
                sys.stdout.flush()
                return "".join(chars)

            if ch == "\003":
                raise KeyboardInterrupt

            if ch in ("\b", "\x7f"):
                if chars:
                    chars.pop()
                    sys.stdout.write("\b \b")
                    sys.stdout.flush()
                continue

            if ch in ("\x00", "\xe0"):
                _ = msvcrt.getwch()
                continue

            if not ch.isprintable():
                continue

            if len(chars) >= max_len:
                continue

            chars.append(ch)
            sys.stdout.write("#")
            sys.stdout.flush()

    except KeyboardInterrupt:
        raise
    except Exception:
        pw = getpass(prompt).strip()
        return pw[:max_len]


def _prompt_new_password() -> str:
    """
    Enforce <= 6 characters. (User requirement: 'at most 6')
    """
    while True:
        new_pw = _prompt_masked_password(
            f"NEW PASSWORD (max {MAX_PASSWORD_LEN} chars): ",
            MAX_PASSWORD_LEN,
        ).strip()
        if not new_pw:
            print("Password cannot be empty.")
            continue
        if len(new_pw) > MAX_PASSWORD_LEN:
            print(f"Password too long. Max is {MAX_PASSWORD_LEN}.")
            continue

        confirm = _prompt_masked_password(
            "CONFIRM NEW PASSWORD: ",
            MAX_PASSWORD_LEN,
        ).strip()
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
    user_id = _normalize_user_id(raw)

    user = _get_user_any(ur, user_id)
    if not user:
        raise RuntimeError("AUTH_FAILED")

    pw = _prompt_masked_password("REA LOGIN | password: ", MAX_PASSWORD_LEN).strip()

    if len(pw) > MAX_PASSWORD_LEN:
        raise RuntimeError("AUTH_FAILED")

    if pw == INITIAL_PASSWORD:
        print("FIRST_LOGIN_PASSWORD_CHANGE_REQUIRED")
        new_pw = _prompt_new_password()
        changed = _change_password_any(ur, user_id, new_pw)
        if changed is not True:
            raise RuntimeError("PASSWORD_CHANGE_FAILED")

        user = _get_user_any(ur, user_id) or user

    else:
        ok = _verify_password_any(ur, user, pw)
        if ok is not True:
            raise RuntimeError("AUTH_FAILED")

        must_change = user.get("must_change_password") or user.get("first_login_change_required")
        if must_change:
            print("FIRST_LOGIN_PASSWORD_CHANGE_REQUIRED")
            new_pw = _prompt_new_password()
            changed = _change_password_any(ur, user_id, new_pw)
            if changed is not True:
                raise RuntimeError("PASSWORD_CHANGE_FAILED")
            user = _get_user_any(ur, user_id) or user
            user = _get_user_any(ur, user_id) or user

    normalized_user_id = _normalize_user_id(user.get("user_id", user_id))

    return {
        "user_id": normalized_user_id,
        "display_name": str(user.get("display_name", "Unknown")),
        "role": str(user.get("role", "operator")),
        "unit_code": str(user.get("unit_code", "CORE")),
        "home_branch": str(user.get("home_branch", "main")),
    }