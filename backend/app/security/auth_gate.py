"""
Authoritative authentication gate for CSS / REA Capital Trading Engine.

PCNRASS Pack 4 fixes:
- Do not crash on import.
- Work with user_registry whether it returns a dataclass, dict, or raises on failure.
- Align password policy with user_registry: minimum 6 characters, no unsafe 6-character maximum.
- Treat authenticate(...) returning a UserRecord as successful authentication.
- Treat change_password(...) returning None as successful if no exception is raised.
- Preserve the engine-facing await_login_ready_state() -> dict contract.
"""

from __future__ import annotations

from getpass import getpass
import importlib
from typing import Any, Dict, Optional


INITIAL_PASSWORD = "123456"
MIN_PASSWORD_LEN = 6
MAX_PASSWORD_LEN = 64


def _safe_import_user_registry():
    try:
        return importlib.import_module("backend.app.security.user_registry")
    except Exception:
        return None


def _coerce_user_record(raw: Any) -> Optional[Dict[str, Any]]:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    d = getattr(raw, "__dict__", None)
    if isinstance(d, dict):
        return d
    return None


def _candidate_user_keys(user_id: int | str) -> list[str]:
    raw = str(user_id).strip()
    keys = []
    if raw:
        keys.append(raw)
    try:
        as_int = int(raw)
        keys.append(str(as_int))
        keys.append(str(as_int).zfill(5))
    except Exception:
        pass
    out = []
    for key in keys:
        if key not in out:
            out.append(key)
    return out


def _get_user_any(ur_mod, user_id: int | str) -> Optional[Dict[str, Any]]:
    if ur_mod is None:
        return None

    for fn_name in ("get_user", "find_user"):
        fn = getattr(ur_mod, fn_name, None)
        if callable(fn):
            for key in _candidate_user_keys(user_id):
                try:
                    rec = _coerce_user_record(fn(key))
                    if rec:
                        return rec
                except Exception:
                    continue

    for fn_name in ("load_users", "_load_users"):
        fn = getattr(ur_mod, fn_name, None)
        if callable(fn):
            try:
                users = fn()
                if isinstance(users, dict):
                    for key in _candidate_user_keys(user_id):
                        rec = _coerce_user_record(users.get(key))
                        if rec:
                            return rec
                if isinstance(users, list):
                    for u in users:
                        ud = _coerce_user_record(u)
                        if ud and str(ud.get("user_id")) in _candidate_user_keys(user_id):
                            return ud
            except Exception:
                continue

    return None


def _verify_password_any(ur_mod, user: Dict[str, Any], password: str) -> bool:
    if ur_mod is None:
        return False

    user_id = user.get("user_id")

    fn = getattr(ur_mod, "authenticate", None)
    if callable(fn):
        for key in _candidate_user_keys(user_id):
            try:
                out = fn(key, password)
                # user_registry.authenticate returns UserRecord on success, not True.
                return _coerce_user_record(out) is not None or out is True
            except Exception:
                continue
        return False

    fn = getattr(ur_mod, "verify_password", None)
    if callable(fn):
        try:
            return bool(fn(user, password))
        except Exception:
            return False

    stored = user.get("password") or user.get("temp_password")
    return isinstance(stored, str) and stored == password


def _change_password_any(ur_mod, user_id: int | str, new_pw: str) -> bool:
    if ur_mod is None:
        return False

    for fn_name in ("change_password", "set_password"):
        fn = getattr(ur_mod, fn_name, None)
        if callable(fn):
            for key in _candidate_user_keys(user_id):
                try:
                    out = fn(key, new_pw)
                    # user_registry.change_password returns None on success.
                    return True if out is None else bool(out)
                except Exception:
                    continue
    return False


def _prompt_new_password() -> str:
    while True:
        new_pw = getpass(f"NEW PASSWORD ({MIN_PASSWORD_LEN}-{MAX_PASSWORD_LEN} chars): ").strip()
        if len(new_pw) < MIN_PASSWORD_LEN:
            print(f"Password too short. Minimum is {MIN_PASSWORD_LEN}.")
            continue
        if len(new_pw) > MAX_PASSWORD_LEN:
            print(f"Password too long. Maximum is {MAX_PASSWORD_LEN}.")
            continue
        if new_pw == INITIAL_PASSWORD:
            print("Password cannot remain the initial default password.")
            continue

        confirm = getpass("CONFIRM NEW PASSWORD: ").strip()
        if new_pw != confirm:
            print("Passwords do not match.")
            continue
        return new_pw


def await_login_ready_state() -> Dict[str, Any]:
    ur = _safe_import_user_registry()
    if ur is None:
        raise RuntimeError("AUTH_REGISTRY_IMPORT_FAILED")

    raw = input("CSS LOGIN | user_id (numeric): ").strip()
    if not raw:
        raise RuntimeError("INVALID_USER_ID")

    user = _get_user_any(ur, raw)
    if not user:
        raise RuntimeError("AUTH_FAILED")

    pw = getpass("CSS LOGIN | password: ").strip()

    ok = _verify_password_any(ur, user, pw)
    if not ok:
        raise RuntimeError("AUTH_FAILED")

    must_change = bool(user.get("must_change_password") or user.get("first_login_change_required"))
    if must_change or pw == INITIAL_PASSWORD:
        print("FIRST_LOGIN_PASSWORD_CHANGE_REQUIRED")
        new_pw = _prompt_new_password()
        changed = _change_password_any(ur, user.get("user_id", raw), new_pw)
        if changed is not True:
            raise RuntimeError("PASSWORD_CHANGE_FAILED")
        user = _get_user_any(ur, raw) or user

    user_id_value = user.get("user_id", raw)

    return {
        "user_id": str(user_id_value).zfill(5),
        "display_name": str(user.get("display_name", "CSS User")),
        "role": str(user.get("role", "VIEWER")),
        "unit_code": str(user.get("unit_code", "CORE")),
        "home_branch": str(user.get("home_branch", "HQ")),
    }
