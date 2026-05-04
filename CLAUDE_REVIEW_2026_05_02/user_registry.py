# backend/app/security/user_registry.py

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict


PROJECT_ROOT = Path(__file__).resolve().parents[3]
USER_STORE = PROJECT_ROOT / "data" / "users.json"


@dataclass
class UserRecord:
    user_id: str
    display_name: str
    role: str
    unit_code: str
    home_branch: str
    password_hash: str
    must_change_password: bool = True


def _normalize_user_id(user_id: int | str) -> str:
    raw = str(user_id).strip()
    try:
        return str(int(raw)).zfill(5)
    except Exception:
        return raw.zfill(5)


def _candidate_keys(user_id: int | str) -> list[str]:
    normalized = _normalize_user_id(user_id)
    keys = [normalized]
    try:
        keys.append(str(int(str(user_id).strip())))
    except Exception:
        pass
    raw = str(user_id).strip()
    if raw:
        keys.append(raw)
    out = []
    for key in keys:
        if key not in out:
            out.append(key)
    return out


def _hash_password(password: str) -> str:
    return hashlib.sha256(str(password).encode("utf-8")).hexdigest()


def _default_users() -> Dict[str, dict]:
    return {
        "00000": {
            "user_id": "00000",
            "display_name": "CSS Administrator",
            "role": "SUPER_USER",
            "unit_code": "CORE",
            "home_branch": "HQ",
            "password_hash": _hash_password("123456"),
            "must_change_password": True,
        }
    }


def _load_users() -> Dict[str, dict]:
    USER_STORE.parent.mkdir(parents=True, exist_ok=True)
    if not USER_STORE.exists():
        users = _default_users()
        _save_users(users)
        return users

    with USER_STORE.open("r", encoding="utf-8") as f:
        users = json.load(f)

    if not isinstance(users, dict):
        users = {}

    changed = False

    # Ensure administrative fallback exists only when absent.
    if "00000" not in users and "0" not in users:
        users.update(_default_users())
        changed = True

    normalized_users: Dict[str, dict] = {}
    for key, record in users.items():
        if not isinstance(record, dict):
            continue
        norm_key = _normalize_user_id(record.get("user_id", key))
        record["user_id"] = norm_key
        normalized_users[norm_key] = record
        if norm_key != key:
            changed = True

    users = normalized_users

    if changed:
        _save_users(users)

    return users


def _save_users(users: Dict[str, dict]) -> None:
    USER_STORE.parent.mkdir(parents=True, exist_ok=True)
    with USER_STORE.open("w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)


def load_users() -> Dict[str, dict]:
    return _load_users()


def get_user(user_id: int | str) -> UserRecord:
    users = _load_users()
    for key in _candidate_keys(user_id):
        if key in users:
            return UserRecord(**users[key])
    raise RuntimeError("AUTH_FAIL: unknown user")


def authenticate(user_id: int | str, password: str) -> UserRecord:
    record = get_user(user_id)
    if record.password_hash != _hash_password(password):
        raise RuntimeError("AUTH_FAIL: bad_password")
    return record


def change_password(user_id: int | str, new_password: str) -> None:
    if len(str(new_password)) < 6:
        raise RuntimeError("PASSWORD_POLICY_VIOLATION: min_length=6")
    if str(new_password) == "123456":
        raise RuntimeError("PASSWORD_POLICY_VIOLATION: cannot_use_default")

    users = _load_users()
    found_key = None
    for key in _candidate_keys(user_id):
        if key in users:
            found_key = key
            break

    if found_key is None:
        raise RuntimeError("AUTH_FAIL: unknown user")

    users[found_key]["password_hash"] = _hash_password(new_password)
    users[found_key]["must_change_password"] = False
    _save_users(users)


def create_user(
    user_id: int | str,
    display_name: str,
    role: str,
    unit_code: str,
    home_branch: str,
    temp_password: str,
) -> None:
    if len(str(temp_password)) < 6:
        raise RuntimeError("PASSWORD_POLICY_VIOLATION: min_length=6")

    users = _load_users()
    key = _normalize_user_id(user_id)

    if key in users:
        raise RuntimeError("USER_ALREADY_EXISTS")

    record = UserRecord(
        user_id=key,
        display_name=display_name,
        role=role,
        unit_code=unit_code,
        home_branch=home_branch,
        password_hash=_hash_password(temp_password),
        must_change_password=True,
    )

    users[key] = asdict(record)
    _save_users(users)
