"""
ops/create_user.py

Create a branch-scoped user and issue a temporary password.

Usage:
  python ops/create_user.py 2001 "Trader A" operator OPS main
  python ops/create_user.py 2002 "Ops Admin" admin OPS main

Output:
- Prints TEMP_PASSWORD once.
- User must change password at first login.
"""

from __future__ import annotations

import sys

from backend.app.security.user_registry import create_user


def main():
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
