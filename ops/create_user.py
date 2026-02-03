"""
ops/create_user.py

Create a branch-scoped user and issue a temporary password.

Fix:
- Makes imports robust by adding repo root to sys.path when run as a script.

Usage:
  python ops/create_user.py 2001 "Trader A" operator OPS main
  python ops/create_user.py 2002 "Ops Admin" admin OPS main
  python ops/create_user.py 2003 "Trader B" operator TRADING main
"""

from __future__ import annotations

import os
import sys


def _bootstrap_repo_root() -> None:
    # ops/ is one level below repo root
    here = os.path.abspath(os.path.dirname(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)


_bootstrap_repo_root()

from backend.app.security.user_registry import create_user  # noqa: E402


def main() -> None:
    if len(sys.argv) < 6:
        print('Usage: python ops/create_user.py <user_id> "<display_name>" <role> <unit_code> <home_branch>')
        sys.exit(2)

    user_id = sys.argv[1].strip()
    display_name = sys.argv[2].strip()
    role = sys.argv[3].strip()
    unit_code = sys.argv[4].strip()
    home_branch = sys.argv[5].strip()

    temp_pw = create_user(
        user_id=user_id,
        display_name=display_name,
        role=role,
        unit_code=unit_code,
        home_branch=home_branch,
    )

    print("USER_CREATED")
    print(f"- user_id: {user_id}")
    print(f"- display_name: {display_name}")
    print(f"- role: {role}")
    print(f"- unit_code: {unit_code}")
    print(f"- home_branch: {home_branch}")
    print("")
    print("TEMP_PASSWORD_ISSUED (one-time display):")
    print(temp_pw)
    print("ACTION_REQUIRED: user must change password on first login.")


if __name__ == "__main__":
    main()
