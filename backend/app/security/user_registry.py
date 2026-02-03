"""
backend/app/security/user_registry.py

User identity + branch-scoped permission registry.

Rules:
- User IDs are numeric strings (e.g., "1369")
- Super user bypasses branch restriction
- Other users are restricted to their home_branch (the branch where they were created)
- Registry stored in runtime/users.json by default (override with REA_USERS_DB_PATH)

This module is dependency-light and safe for CLI + deployment.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Any


DEFAULT_USERS_DB_PATH = os.getenv("REA_USERS_DB_PATH", r"runtime\users.json")
SUPERUSER_ID = "1369"


@dataclass(frozen=True)
class UserRecord:
    user_id: str               # numeric string
    display_name: str
    role: str                  # "superuser" | "admin" | "operator" | etc
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
    Works from repo root.
    """
    # Allow explicit override (CI/CD or production)
    env_branch = os.getenv("REA_GIT_BRANCH", "").strip()
    if env_branch:
        return env_branch

    head = Path(".git") / "HEAD"
    try:
        content = _read_text(head).strip()
        # Typical: "ref: refs/heads/main"
        if content.startswith("ref:"):
            ref = content.split(":", 1)[1].strip()
            return ref.split("/")[-1]
        # Detached head (commit hash)
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
        users[str(uid)] = UserRecord(
            user_id=str(uid),
            display_name=str(u.get("display_name", "")),
            role=str(u.get("role", "operator")),
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
            "home_branch": u.home_branch,
            "is_active": u.is_active,
        }
    _write_text(p, json.dumps(payload, indent=2, sort_keys=True))


def ensure_superuser_exists(db_path: str = DEFAULT_USERS_DB_PATH) -> None:
    users = load_users(db_path)
    if SUPERUSER_ID in users:
        return
    # Create super user record (branch-independent by role)
    branch = get_current_branch()
    users[SUPERUSER_ID] = UserRecord(
        user_id=SUPERUSER_ID,
        display_name="Robert Asibor",
        role="superuser",
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
    role: str = "operator",
    db_path: str = DEFAULT_USERS_DB_PATH,
) -> UserRecord:
    """
    Create a user on the CURRENT branch. Enforces unique ID.
    """
    uid = str(user_id).strip()
    if not uid.isdigit():
        raise ValueError("user_id must be numeric")

    users = load_users(db_path)
    if uid in users:
        raise ValueError(f"user_id already exists: {uid}")

    branch = get_current_branch()
    rec = UserRecord(
        user_id=uid,
        display_name=display_name.strip(),
        role=role.strip(),
        home_branch=branch,
        is_active=True,
    )
    users[uid] = rec
    save_users(users, db_path)
    return rec


def branch_allowed(user: UserRecord, current_branch: str) -> bool:
    """
    Branch restriction logic.
    - superuser: always allowed
    - others: only allowed on home_branch
    """
    if not user.is_active:
        return False
    if user.role.lower() == "superuser":
        return True
    return user.home_branch == current_branch
