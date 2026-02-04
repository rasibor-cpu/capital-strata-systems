from __future__ import annotations

import json
import os
from dataclasses import asdict, is_dataclass
from getpass import getpass
from typing import Any, Dict, Optional, Tuple


# -----------------------------
# Storage (single source of truth)
# Prefer runtime\users.json if present; fallback to data\users.json.
# -----------------------------
def _users_path() -> str:
    runtime_path = os.path.join("runtime", "users.json")
    data_path = os.path.join("data", "users.json")
    if os.path.exists(runtime_path):
        return runtime_path
    if os.path.exists(data_path):
        return data_path
    # default: create runtime/users.json
    os.makedirs("runtime", exist_ok=True)
    return runtime_path


def _load_users() -> Dict[str, Any]:
    path = _users_path()
    if not os.path.exists(path):
        return {"users": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_users(doc: Dict[str, Any]) -> None:
    path = _users_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, sort_keys=True)


def _to_dict(obj: Any) -> Dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if is_dataclass(obj):
        return asdict(obj)
    # last resort
    return dict(obj) if hasattr(obj, "items") else {"value": str(obj)}


def _find_user(doc: Dict[str, Any], user_id: int) -> Optional[Dict[str, Any]]:
    users = doc.get("users", [])
    for u in users:
        try:
            if int(u.get("user_id")) == int(user_id):
                return u
        except Exception:
            continue
    return None


# -----------------------------
# Optional integration with user_registry.py (if functions exist)
# -----------------------------
def _user_registry_module():
    try:
        from backend.app.security import user_registry  # type: ignore
        return user_registry
    except Exception:
        return None


def _ur_authenticate(user_id: int, password: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Try to authenticate via user_registry if available.
    Return: (ok, reason, user_dict)
    """
    ur = _user_registry_module()
    if not ur:
        return False, "user_registry_missing", None

    # Prefer a single call if provided by your registry
    fn = getattr(ur, "authenticate", None) or getattr(ur, "authenticate_user", None)
    if callable(fn):
        try:
            out = fn(user_id, password)
            # Allow registry to return (ok, reason, user) OR dict OR bool
            if isinstance(out, tuple) and len(out) == 3:
                ok, reason, user = out
                return bool(ok), str(reason), _to_dict(user)
            if isinstance(out, tuple) and len(out) == 2:
                ok, reason = out
                return bool(ok), str(reason), None
            if isinstance(out, dict):
                # assume {"ok":..., "reason":..., "user":...}
                return bool(out.get("ok", False)), str(out.get("reason", "unknown")), _to_dict(out.get("user"))
            if isinstance(out, bool):
                return out, "ok" if out else "bad_password", None
            return False, "unexpected_auth_return", None
        except Exception as e:
            return False, f"auth_exception:{e}", None

    return False, "no_auth_fn", None


def _ur_change_password(user_id: int, old_pw: str, new_pw: str) -> Tuple[bool, str]:
    ur = _user_registry_module()
    if not ur:
        return False, "user_registry_missing"

    fn = getattr(ur, "change_password", None) or getattr(ur, "set_password", None)
    if callable(fn):
        try:
            out = fn(user_id, old_pw, new_pw) if fn.__code__.co_argcount >= 3 else fn(user_id, new_pw)
            if isinstance(out, tuple) and len(out) == 2:
                return bool(out[0]), str(out[1])
            if isinstance(out, bool):
                return out, "ok" if out else "failed"
            if isinstance(out, dict):
                return bool(out.get("ok", False)), str(out.get("reason", "unknown"))
            return False, "unexpected_change_return"
        except Exception as e:
            return False, f"change_exception:{e}"

    return False, "no_change_fn"


# -----------------------------
# Auth gate public API
# -----------------------------
def await_login_ready_state() -> Dict[str, Any]:
    """
    Blocks until valid credentials are provided.
    Returns a user context dict used by run_live_guarded.
    """
    # Hard rule: user_id must be numeric
    while True:
        raw_id = input("REA LOGIN | user_id (numeric): ").strip()
        try:
            user_id = int(raw_id)
        except Exception:
            print("user_id must be numeric.")
            continue

        pw = getpass("REA LOGIN | password: ").strip()

        # 1) try registry-based auth (preferred)
        ok, reason, user_from_registry = _ur_authenticate(user_id, pw)

        if ok:
            user_ctx = user_from_registry or _load_user_ctx_from_file(user_id)
            user_ctx["user_id"] = user_id

            # First-login password change policy (min 6 chars)
            if _needs_first_login_change(user_ctx):
                _force_first_login_password_change(user_id, pw, user_ctx)

            return _finalize_user_ctx(user_ctx)

        # 2) fallback: file-based auth if registry missing / not wired
        if reason in ("user_registry_missing", "no_auth_fn", "unexpected_auth_return", "no_auth_fn"):
            ok2, user_ctx2 = _file_authenticate(user_id, pw)
            if ok2:
                if _needs_first_login_change(user_ctx2):
                    _force_first_login_password_change(user_id, pw, user_ctx2)
                return _finalize_user_ctx(user_ctx2)

        print(f"LOGIN_FAIL | user_id={user_id} | reason={reason}")
        print("Invalid credentials.")


def _load_user_ctx_from_file(user_id: int) -> Dict[str, Any]:
    doc = _load_users()
    u = _find_user(doc, user_id)
    return dict(u) if u else {}


def _file_authenticate(user_id: int, password: str) -> Tuple[bool, Dict[str, Any]]:
    doc = _load_users()
    u = _find_user(doc, user_id)
    if not u:
        return False, {}
    # user record stores either "password" (plain for now) or "password_hash"
    # We support "password" for the current bootstrap stage.
    stored = (u.get("password") or "").strip()
    if stored and stored == password:
        return True, dict(u)
    # If password not stored (e.g., registry uses hashed only), fail here.
    return False, {}


def _needs_first_login_change(user_ctx: Dict[str, Any]) -> bool:
    # Accept multiple flags so we don’t break if naming differs across versions
    return bool(
        user_ctx.get("must_change_password")
        or user_ctx.get("first_login_change_required")
        or user_ctx.get("temp_password_issued")
        or user_ctx.get("first_login", False)
    )


def _force_first_login_password_change(user_id: int, old_pw: str, user_ctx: Dict[str, Any]) -> None:
    print("FIRST_LOGIN_PASSWORD_CHANGE_REQUIRED")
    while True:
        new_pw = getpass("NEW PASSWORD (min 6 chars): ").strip()
        if len(new_pw) < 6:
            print("Password must be at least 6 characters.")
            continue
        confirm = getpass("CONFIRM NEW PASSWORD: ").strip()
        if confirm != new_pw:
            print("Passwords do not match.")
            continue

        # Try registry change first
        ok, reason = _ur_change_password(user_id, old_pw, new_pw)
        if ok:
            print("PASSWORD CHANGED SUCCESSFULLY")
            return

        # Fallback: file update (bootstrap)
        if reason in ("user_registry_missing", "no_change_fn", "unexpected_change_return", "no_change_fn"):
            doc = _load_users()
            u = _find_user(doc, user_id)
            if not u:
                print("Cannot update password (user missing in file store).")
                return
            u["password"] = new_pw
            u["must_change_password"] = False
            u["first_login_change_required"] = False
            u["temp_password_issued"] = False
            _save_users(doc)
            print("PASSWORD CHANGED SUCCESSFULLY")
            return

        print(f"PASSWORD CHANGE FAILED: {reason}")


def _finalize_user_ctx(user_ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enforce required fields and defaults.
    """
    # Mandatory fields (with safe defaults for bootstrap)
    role = (user_ctx.get("role") or "operator").strip()
    unit_code = (user_ctx.get("unit_code") or "CORE").strip()
    home_branch = (user_ctx.get("home_branch") or "main").strip()

    out = dict(user_ctx)
    out["role"] = role
    out["unit_code"] = unit_code
    out["home_branch"] = home_branch
    return out
