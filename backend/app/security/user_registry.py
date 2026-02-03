"""
backend/app/security/user_registry.py

User identity + branch-scoped permission registry.

Rules:
- User IDs are numeric strings (e.g., "1369")
- Super user bypasses branch restriction
- Other users are restricted to their home_branch (the branch where the user was created)
- Each user has a unit_code that maps to allowed screens/functions via unit_router
- Registry stored in runtime/users.json by default (override with REA_USERS_DB_PATH)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Any

from backend.app.security.unit_router import resolve_unit_bundle, list_unit_codes

DEFAULT_USERS_DB_PATH = os.getenv("REA_USERS_DB_PATH", r"runtime\users.json")
SUPERUSER_ID = "1369"


@dataclass(frozen=True)
class UserRecord:
    user_id: str               # numeric string
    display_name: str
    role: str                  # "superuser" | "admin" | "operator" | etc
    unit_code: str             # OPS, RISK, FINCTRL, TRADING_DESK, COMPLIANCE (or SUPER)
    home_branch: str           # branch where the user was created
    is_active: bool = True


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def get_current_branch() -> str:
    """
    Resolve current git branch without calling git executable.
    Works from repo root. Allows override via REA_GIT_BRANCH.
    """
    env_branch = os.getenv("REA_GIT_BRANCH", "").strip()
    if env_branch:
        return env_branch

    head = Path(".git") / "HEAD"
    try:
        content = _read_text(head).strip()
        if content.startswith("ref:"):
            ref = content.split(":", 1)[1].strip()
            return ref.split("/")[-1]
        return "DETACHED"
    except Exception:
        return "UNKNOWN"


def load_users(db_path: str = DEFAULT_USERS_DB_PATH) -> Dict[str, UserRecord]:
    p = Path(db_path)
    if not p.exists():
        return {}

    raw = json.loads(_read_text(p))
    users: Dict[str, UserRecord] = {}

    for uid, u in raw.get("users", {}).items():
        unit_code = str(u.get("unit_code", "")).strip().upper()

        # Validate unit_code (fail-closed if invalid)
        # SUPER is allowed for superuser
        if unit_code and unit_code != "SUPER":
            resolve_unit_bundle(unit_code)

        users[str(uid)] = UserRecord(
            user_id=str(uid),
            display_name=str(u.get("display_name", "")),
            role=str(u.get("role", "operator")),
            unit_code=unit_code,
            home_branch=str(u.get("home_branch", "UNKNOWN")),
            is_active=bool(u.get("is_active", True)),
        )

    return users


def save_users(users: Dict[str, UserRecord], db_path: str = DEFAULT_USERS_DB_PATH) -> None:
    p = Path(db_path)
    payload: Dict[str, Any] = {"users": {}}
    for uid, u in users.items():
        payload["users"][uid] = {
            "display_name": u.display_name,
            "role": u.role,
            "unit_code": u.unit_code,
            "home_branch": u.home_branch,
            "is_active": u.is_active,
        }
    _write_text(p, json.dumps(payload, indent=2, sort_keys=True))


def ensure_superuser_exists(db_path: str = DEFAULT_USERS_DB_PATH) -> None:
    users = load_users(db_path)
    if SUPERUSER_ID in users:
        return

    branch = get_current_branch()
    users[SUPERUSER_ID] = UserRecord(
        user_id=SUPERUSER_ID,
        display_name="Robert Asibor",
        role="superuser",
        unit_code="SUPER",
        home_branch=branch,
        is_active=True,
    )
    save_users(users, db_path)


def get_user(user_id: str, db_path: str = DEFAULT_USERS_DB_PATH) -> Optional[UserRecord]:
    users = load_users(db_path)
    return users.get(str(user_id))


def create_user(
    user_id: str,
    display_name: str,
    unit_code: str,
    role: str = "operator",
    db_path: str = DEFAULT_USERS_DB_PATH,
) -> UserRecord:
    """
    Create a user on the CURRENT branch. Enforces unique numeric ID and known unit_code.
    """
    uid = str(user_id).strip()
    if not uid.isdigit():
        raise ValueError("user_id must be numeric")

    if uid == SUPERUSER_ID:
        raise ValueError(f"user_id {SUPERUSER_ID} is reserved for superuser")

    code = (unit_code or "").strip().upper()
    if not code:
        raise ValueError(f"unit_code is required. Allowed: {', '.join(list_unit_codes())}")

    if code != "SUPER":
        resolve_unit_bundle(code)

    users = load_users(db_path)
    if uid in users:
        raise ValueError(f"user_id already exists: {uid}")

    branch = get_current_branch()
    rec = UserRecord(
        user_id=uid,
        display_name=display_name.strip(),
        role=role.strip(),
        unit_code=code,
        home_branch=branch,
        is_active=True,
    )
    users[uid] = rec
    save_users(users, db_path)
    return rec


def branch_allowed(user: UserRecord, current_branch: str) -> bool:
    """
    Branch restriction logic:
    - superuser: always allowed
    - others: only allowed on home_branch
    """
    if not user.is_active:
        return False
    if user.role.lower() == "superuser":
        return True
    return user.home_branch == current_branch
