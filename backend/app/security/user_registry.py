# backend/app/security/user_registry.py

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from typing import Dict

USER_STORE = os.path.join("data", "users.json")
LOGGER = logging.getLogger(__name__)


@dataclass
class UserRecord:
    user_id: int
    display_name: str
    role: str
    unit_code: str
    home_branch: str
    password_hash: str
    must_change_password: bool = True


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _load_users() -> Dict[str, dict]:
    if not os.path.exists(USER_STORE):
        return {}
    with open(USER_STORE, "r") as f:
        return json.load(f)


def _save_users(users: Dict[str, dict]) -> None:
    os.makedirs(os.path.dirname(USER_STORE), exist_ok=True)
    with open(USER_STORE, "w") as f:
        json.dump(users, f, indent=2)


def load_users() -> Dict[str, dict]:
    return _load_users()


def get_user(user_id: int) -> UserRecord | None:
    users = _load_users()
    record = users.get(str(user_id))
    if record is None:
        return None
    return UserRecord(**record)


def authenticate(user_id: int, password: str) -> UserRecord:
    users = _load_users()
    key = str(user_id)

    if key not in users:
        raise RuntimeError("AUTH_FAIL: unknown user")

    record = users[key]
    if record["password_hash"] != _hash_password(password):
        raise RuntimeError("AUTH_FAIL: bad_password")

    return UserRecord(**record)


def change_password(user_id: int, new_password: str) -> bool:
    if len(new_password) < 6:
        raise RuntimeError("PASSWORD_POLICY_VIOLATION: min_length=6")

    users = _load_users()
    key = str(user_id)

    if key not in users:
        raise RuntimeError("AUTH_FAIL: unknown user")

    users[key]["password_hash"] = _hash_password(new_password)
    users[key]["must_change_password"] = False
    _save_users(users)
    return True


def reset_password(
    user_id: int,
    temporary_password: str,
    *,
    authorized_by_role: str,
    require_change: bool = True,
) -> bool:
    if str(authorized_by_role or "").strip().upper() not in {
        "ADMIN",
        "SUPERUSER",
        "SUPER_USER",
    }:
        LOGGER.warning(
            "PASSWORD_RESET_BLOCKED | user_id=%s | reason=unauthorized_role",
            user_id,
        )
        raise PermissionError("PASSWORD_RESET_FORBIDDEN")

    if len(temporary_password) < 6:
        LOGGER.warning(
            "PASSWORD_RESET_BLOCKED | user_id=%s | reason=password_policy",
            user_id,
        )
        raise RuntimeError("PASSWORD_POLICY_VIOLATION: min_length=6")

    users = _load_users()
    key = str(user_id)

    if key not in users:
        LOGGER.warning(
            "PASSWORD_RESET_BLOCKED | user_id=%s | reason=unknown_user",
            user_id,
        )
        raise RuntimeError("AUTH_FAIL: unknown user")

    users[key]["password_hash"] = _hash_password(temporary_password)
    users[key]["must_change_password"] = bool(require_change)
    _save_users(users)
    LOGGER.info(
        "PASSWORD_RESET_COMPLETED | user_id=%s | authorized_by_role=%s | require_change=%s",
        user_id,
        str(authorized_by_role or "").strip().upper(),
        bool(require_change),
    )
    return True


def create_user(
    user_id: int,
    display_name: str,
    role: str,
    unit_code: str,
    home_branch: str,
    temp_password: str,
) -> None:
    users = _load_users()
    key = str(user_id)

    if key in users:
        raise RuntimeError("USER_ALREADY_EXISTS")

    users[key] = {
        "user_id": user_id,
        "display_name": display_name,
        "role": role,
        "unit_code": unit_code,
        "home_branch": home_branch,
        "password_hash": _hash_password(temp_password),
        "must_change_password": True,
    }

    _save_users(users)
