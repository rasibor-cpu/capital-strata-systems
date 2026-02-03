"""
backend/app/security/user_registry.py

User registry with:
- Branch scoping
- Unit codes
- Temp password issuance
- Mandatory first-login password change
- Password policy: MIN_LENGTH = 6
"""

from __future__ import annotations

import json
import os
import secrets
import hashlib
import time
from dataclasses import dataclass
from typing import Dict, Optional

USERS_FILE = os.path.join("runtime", "users.json")
MIN_PASSWORD_LEN = 6  # <<< POLICY FIX


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


def _ensure_store() -> None:
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)


def _load() -> Dict[str, UserRecord]:
    _ensure_store()
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return {k: UserRecord(**v) for k, v in raw.items()}


def _save(users: Dict[str, UserRecord]) -> None:
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump({k: vars(v) for k, v in users.items()}, f, indent=2)


def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


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
    return rec.role == "superuser" or rec.home_branch == current_branch


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
    rec = users[user_id]
    rec.password_hash = _hash(new_password)
    rec.first_login_required = False
    users[user_id] = rec
    _save(users)


def get_current_branch() -> str:
    return os.getenv("REA_ENGINE_BRANCH", "main")
