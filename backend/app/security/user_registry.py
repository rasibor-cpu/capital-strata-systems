"""
backend/app/security/user_registry.py

Branch-scoped user registry with:
- schema-tolerant load (handles legacy / double-nested records)
- auto-normalization on load (rewrites to canonical shape)
- temp password issuance
- mandatory first-login password change
- password policy: MIN_PASSWORD_LEN = 6
"""

from __future__ import annotations

import json
import os
import secrets
import hashlib
import time
from dataclasses import dataclass
from typing import Dict, Optional, Any

USERS_FILE = os.path.join("runtime", "users.json")
MIN_PASSWORD_LEN = 6  # policy


@dataclass
class UserRecord:
    user_id: str
    display_name: str
    role: str
    unit_code: str
    home_branch: str
    password_hash: str
    first_login_required: bool
    created_at: float


CANON_KEYS = {
    "user_id",
    "display_name",
    "role",
    "unit_code",
    "home_branch",
    "password_hash",
    "first_login_required",
    "created_at",
}


def _ensure_store() -> None:
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)


def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


def _unwrap_legacy_record(user_id: str, v: Any) -> Dict[str, Any]:
    """
    Accepts several legacy shapes and returns a canonical dict of record fields.

    Canonical:
      v = {"user_id": "...", "display_name": "...", ...}

    Legacy (double-nested):
      v = {"1369": {"user_id":"1369", ...}}

    Legacy (extra wrapper):
      v = {"record": {...}}  (we ignore unknown wrappers by scanning for CANON_KEYS)
    """
    if isinstance(v, dict):
        # Double-nested by user_id
        if user_id in v and isinstance(v[user_id], dict):
            v = v[user_id]

        # If it's still not canonical, try to find an inner dict that looks canonical
        if not CANON_KEYS.issubset(set(v.keys())):
            for _, inner in v.items():
                if isinstance(inner, dict) and ("user_id" in inner) and ("password_hash" in inner):
                    v = inner
                    break

        # Filter to canonical keys only (drop junk keys that break dataclass init)
        cleaned = {k: v.get(k) for k in CANON_KEYS if k in v}
        return cleaned

    # Anything else is invalid
    return {}


def _normalize_raw(raw: Any) -> Dict[str, Dict[str, Any]]:
    """
    Returns normalized map: user_id -> record_dict (canonical fields only)
    """
    out: Dict[str, Dict[str, Any]] = {}

    if not isinstance(raw, dict):
        return out

    for uid, v in raw.items():
        if not isinstance(uid, str):
            continue
        rec = _unwrap_legacy_record(uid, v)
        if not rec:
            continue

        # Hard fail-closed: user_id inside record must match key
        if str(rec.get("user_id", "")).strip() != uid.strip():
            continue

        # Ensure required fields exist
        missing = [k for k in CANON_KEYS if k not in rec]
        if missing:
            continue

        out[uid] = rec

    return out


def _load() -> Dict[str, UserRecord]:
    _ensure_store()
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)

    normalized = _normalize_raw(raw)

    # Auto-rewrite to canonical form if file is not already canonical
    # (prevents the same crash from ever happening again)
    if raw != normalized:
        with open(USERS_FILE, "w", encoding="utf-8") as wf:
            json.dump(normalized, wf, indent=2)

    return {uid: UserRecord(**rec) for uid, rec in normalized.items()}


def _save(users: Dict[str, UserRecord]) -> None:
    _ensure_store()
    payload = {uid: vars(rec) for uid, rec in users.items()}
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def ensure_superuser_exists() -> None:
    users = _load()
    if "1369" not in users:
        users["1369"] = UserRecord(
            user_id="1369",
            display_name="Robert Asibor",
            role="superuser",
            unit_code="SUPER",
            home_branch="main",
            password_hash=_hash("CHANGE_ME_NOW_1369"),
            first_login_required=True,
            created_at=time.time(),
        )
        _save(users)


def create_user(
    user_id: str,
    display_name: str,
    role: str,
    unit_code: str,
    home_branch: str,
) -> str:
    users = _load()
    if user_id in users:
        raise ValueError("user already exists")

    temp_pw = secrets.token_urlsafe(8)[:8]

    users[user_id] = UserRecord(
        user_id=user_id,
        display_name=display_name,
        role=role,
        unit_code=unit_code,
        home_branch=home_branch,
        password_hash=_hash(temp_pw),
        first_login_required=True,
        created_at=time.time(),
    )
    _save(users)
    return temp_pw


def get_user(user_id: str) -> Optional[UserRecord]:
    return _load().get(user_id)


def branch_allowed(rec: UserRecord, current_branch: str) -> bool:
    return rec.role.lower() == "superuser" or rec.home_branch == current_branch


def authenticate(user_id: str, password: str) -> UserRecord:
    users = _load()
    rec = users.get(user_id)
    if not rec or _hash(password) != rec.password_hash:
        raise ValueError("bad_password")
    return rec


def change_password(user_id: str, new_password: str, confirm: str) -> None:
    if new_password != confirm:
        raise ValueError("password_mismatch")
    if len(new_password) < MIN_PASSWORD_LEN:
        raise ValueError(f"password_too_short_min_{MIN_PASSWORD_LEN}")

    users = _load()
    if user_id not in users:
        raise ValueError("unknown_user")

    rec = users[user_id]
    rec.password_hash = _hash(new_password)
    rec.first_login_required = False
    users[user_id] = rec
    _save(users)


def get_current_branch() -> str:
    return os.getenv("REA_ENGINE_BRANCH", "main")
