"""
backend/app/security/user_registry.py

User registry with branch-scoped permissions and per-user password support.

Storage:
- runtime/users.json (ignored by git). This is intentional: credentials must not be committed.

Security model:
- Each user has:
  - user_id (string, numeric)
  - role (superuser/admin/operator/...)
  - unit_code (department/unit)
  - home_branch (branch they belong to)
  - must_change_password (bool)
  - password_hash (pbkdf2-hmac-sha256, salted)
"""

from __future__ import annotations

import base64
import json
import os
import secrets
import hashlib
from dataclasses import dataclass
from typing import Optional, Dict, Any


RUNTIME_DIR = "runtime"
USERS_PATH = os.path.join(RUNTIME_DIR, "users.json")

SUPERUSER_ID = "1369"
SUPERUSER_ROLE = "superuser"
SUPERUSER_UNIT = "SUPER"
DEFAULT_BRANCH = "main"


@dataclass(frozen=True)
class UserRecord:
    user_id: str
    display_name: str
    role: str
    unit_code: str
    home_branch: str
    must_change_password: bool


def _ensure_runtime_dir() -> None:
    os.makedirs(RUNTIME_DIR, exist_ok=True)


def _load_users() -> Dict[str, Any]:
    _ensure_runtime_dir()
    if not os.path.exists(USERS_PATH):
        return {"users": {}}
    with open(USERS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_users(db: Dict[str, Any]) -> None:
    _ensure_runtime_dir()
    with open(USERS_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, sort_keys=True)


def _pbkdf2_hash(password: str, salt: bytes) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return base64.b64encode(dk).decode("ascii")


def _new_salt() -> bytes:
    return secrets.token_bytes(16)


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def _unb64(s: str) -> bytes:
    return base64.b64decode(s.encode("ascii"))


def get_current_branch() -> str:
    """
    Branch scoping rule source.
    Priority:
      1) REA_CURRENT_BRANCH env
      2) GIT_BRANCH env
      3) DEFAULT_BRANCH
    """
    b = (os.getenv("REA_CURRENT_BRANCH", "") or os.getenv("GIT_BRANCH", "")).strip()
    return b or DEFAULT_BRANCH


def ensure_superuser_exists() -> None:
    db = _load_users()
    users = db.get("users", {})

    if SUPERUSER_ID in users:
        return

    # Create superuser with a generated temp password (printed once).
    temp_pw = generate_temp_password()
    salt = _new_salt()
    users[SUPERUSER_ID] = {
        "user_id": SUPERUSER_ID,
        "display_name": "Robert Asibor",
        "role": SUPERUSER_ROLE,
        "unit_code": SUPERUSER_UNIT,
        "home_branch": DEFAULT_BRANCH,
        "must_change_password": True,
        "password_salt_b64": _b64(salt),
        "password_hash_b64": _pbkdf2_hash(temp_pw, salt),
    }
    db["users"] = users
    _save_users(db)

    print("SUPERUSER_CREATED | user_id=1369 | TEMP_PASSWORD_ISSUED")
    print(f"SUPERUSER_TEMP_PASSWORD: {temp_pw}")
    print("ACTION_REQUIRED: login once and change password immediately.")


def generate_temp_password() -> str:
    """
    Human-typable but strong-ish temp password.
    """
    # 4 blocks of 4 chars: XXXX-XXXX-XXXX-XXXX
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    blocks = ["".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(4)]
    return "-".join(blocks)


def create_user(
    user_id: str,
    display_name: str,
    role: str,
    unit_code: str,
    home_branch: str,
) -> str:
    """
    Creates a user and returns the generated temporary password.
    """
    if not user_id.isdigit():
        raise ValueError("user_id must be numeric (string).")

    db = _load_users()
    users = db.get("users", {})

    if user_id in users:
        raise ValueError("user_id already exists.")

    temp_pw = generate_temp_password()
    salt = _new_salt()

    users[user_id] = {
        "user_id": user_id,
        "display_name": display_name,
        "role": role,
        "unit_code": unit_code,
        "home_branch": home_branch,
        "must_change_password": True,
        "password_salt_b64": _b64(salt),
        "password_hash_b64": _pbkdf2_hash(temp_pw, salt),
    }

    db["users"] = users
    _save_users(db)
    return temp_pw


def get_user(user_id: str) -> Optional[UserRecord]:
    db = _load_users()
    rec = db.get("users", {}).get(user_id)
    if not rec:
        return None
    return UserRecord(
        user_id=rec["user_id"],
        display_name=rec.get("display_name", ""),
        role=rec.get("role", "operator"),
        unit_code=rec.get("unit_code", "OPS"),
        home_branch=rec.get("home_branch", DEFAULT_BRANCH),
        must_change_password=bool(rec.get("must_change_password", False)),
    )


def branch_allowed(user: UserRecord, current_branch: str) -> bool:
    if user.role.lower() == SUPERUSER_ROLE:
        return True
    return (user.home_branch or DEFAULT_BRANCH) == (current_branch or DEFAULT_BRANCH)


def verify_password(user_id: str, password: str) -> bool:
    db = _load_users()
    rec = db.get("users", {}).get(user_id)
    if not rec:
        return False
    salt = _unb64(rec["password_salt_b64"])
    expected = rec["password_hash_b64"]
    got = _pbkdf2_hash(password, salt)
    return secrets.compare_digest(got, expected)


def set_new_password(user_id: str, new_password: str) -> None:
    if len(new_password) < 10:
        raise ValueError("password too short (min 10 chars).")

    db = _load_users()
    users = db.get("users", {})
    rec = users.get(user_id)
    if not rec:
        raise ValueError("unknown user_id")

    salt = _new_salt()
    rec["password_salt_b64"] = _b64(salt)
    rec["password_hash_b64"] = _pbkdf2_hash(new_password, salt)
    rec["must_change_password"] = False

    users[user_id] = rec
    db["users"] = users
    _save_users(db)
