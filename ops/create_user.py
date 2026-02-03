"""
ops/create_user.py

Create a user in runtime/users.json with branch-scoped permissions.

Usage:
  python ops/create_user.py 2001 "Trader A" operator
  python ops/create_user.py 2002 "Ops Admin" admin

Notes:
- user_id must be numeric and unique
- home_branch auto-resolves from .git/HEAD (or REA_GIT_BRANCH override)
- superuser id 1369 is reserved (Robert Asibor)
- runtime/users.json is intentionally gitignored
"""

from __future__ import annotations

import sys

# Ensure repo root on path (so `backend.*` imports work even when running from ops/)
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.security.user_registry import (
    create_user,
    ensure_superuser_exists,
    load_users,
    get_current_branch,
    SUPERUSER_ID,
)


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: python ops/create_user.py <user_id> \"Full Name\" [role]")
        return 2

    user_id = str(sys.argv[1]).strip()
    display_name = str(sys.argv[2]).strip()
    role = str(sys.argv[3]).strip() if len(sys.argv) >= 4 else "operator"

    if not user_id.isdigit():
        print("ERROR: user_id must be numeric.")
        return 2

    if user_id == SUPERUSER_ID:
        print(f"ERROR: user_id {SUPERUSER_ID} is reserved for superuser (Robert Asibor).")
        return 2

    if not display_name:
        print("ERROR: display_name is required.")
        return 2

    ensure_superuser_exists()

    # Duplicate check (clear error)
    users = load_users()
    if user_id in users:
        u = users[user_id]
        print(f"ERROR: user_id already exists: {user_id} ({u.display_name}, role={u.role}, branch={u.home_branch})")
        return 2

    rec = create_user(user_id=user_id, display_name=display_name, role=role)

    branch = get_current_branch()
    print("USER_CREATED")
    print(f"- user_id:      {rec.user_id}")
    print(f"- display_name: {rec.display_name}")
    print(f"- role:         {rec.role}")
    print(f"- home_branch:  {rec.home_branch}")
    print(f"- current:      {branch}")
    print("")
    print("NOTE: Users are branch-scoped (except superuser).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

