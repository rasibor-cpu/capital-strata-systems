"""
ops/create_user.py

Create a user in runtime/users.json with:
- numeric unique user_id
- unit_code (department/function) that drives screen/function auto-load
- branch-scoped permissions (except superuser)

Usage:
  python ops/create_user.py 2001 "Trader A" TRADING_DESK operator
  python ops/create_user.py 2002 "Ops Admin" OPS admin
  python ops/create_user.py 2003 "Risk Checker" RISK operator

runtime/users.json is intentionally gitignored.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure repo root on path (so backend imports work when running from ops/)
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
from backend.app.security.unit_router import list_unit_codes, resolve_unit_bundle


def main() -> int:
    if len(sys.argv) < 4:
        print("Usage: python ops/create_user.py <user_id> \"Full Name\" <UNIT_CODE> [role]")
        print(f"Allowed UNIT_CODE: {', '.join(list_unit_codes())}")
        return 2

    user_id = str(sys.argv[1]).strip()
    display_name = str(sys.argv[2]).strip()
    unit_code = str(sys.argv[3]).strip().upper()
    role = str(sys.argv[4]).strip() if len(sys.argv) >= 5 else "operator"

    if not user_id.isdigit():
        print("ERROR: user_id must be numeric.")
        return 2

    if user_id == SUPERUSER_ID:
        print(f"ERROR: user_id {SUPERUSER_ID} is reserved for superuser (Robert Asibor).")
        return 2

    if not display_name:
        print("ERROR: display_name is required.")
        return 2

    try:
        bundle = resolve_unit_bundle(unit_code)
    except Exception as e:
        print(f"ERROR: invalid unit_code '{unit_code}'.")
        print(f"Allowed UNIT_CODE: {', '.join(list_unit_codes())}")
        print(f"Detail: {e}")
        return 2

    ensure_superuser_exists()

    users = load_users()
    if user_id in users:
        u = users[user_id]
        print(
            f"ERROR: user_id already exists: {user_id} "
            f"({u.display_name}, role={u.role}, unit={u.unit_code}, branch={u.home_branch})"
        )
        return 2

    rec = create_user(user_id=user_id, display_name=display_name, unit_code=unit_code, role=role)

    branch = get_current_branch()
    print("USER_CREATED")
    print(f"- user_id:      {rec.user_id}")
    print(f"- display_name: {rec.display_name}")
    print(f"- role:         {rec.role}")
    print(f"- unit_code:    {rec.unit_code} ({bundle.label})")
    print(f"- modules:      {', '.join(bundle.modules)}")
    print(f"- home_branch:  {rec.home_branch}")
    print(f"- current:      {branch}")
    print("")
    print("NOTE: Users are branch-scoped (except superuser).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
