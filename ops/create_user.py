# ops/create_user.py
# REA Capital Trading Engine — User Creation Utility
#
# This script is executed as a top-level tool.
# We explicitly bind the project root to sys.path
# so that backend.app.* imports are always resolvable.

from __future__ import annotations

import argparse
import os
import sys
import secrets
import string

# ---------------------------------------------------------------------
# HARD BIND PROJECT ROOT (authoritative, production-safe for ops tools)
# ---------------------------------------------------------------------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ---------------------------------------------------------------------
# Imports (now guaranteed to resolve)
# ---------------------------------------------------------------------
from backend.app.security.user_registry import create_user


def _generate_temp_password(length: int = 14) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def main() -> int:
    parser = argparse.ArgumentParser(description="Create REA system user")
    parser.add_argument("user_id", type=int)
    parser.add_argument("display_name", type=str)
    parser.add_argument("role", type=str)
    parser.add_argument("unit_code", type=str)
    parser.add_argument("home_branch", type=str)
    parser.add_argument("temp_password", nargs="?", default=None)

    args = parser.parse_args()

    temp_pw = args.temp_password or _generate_temp_password()

    try:
        create_user(
            user_id=args.user_id,
            display_name=args.display_name,
            role=args.role,
            unit_code=args.unit_code,
            home_branch=args.home_branch,
            temp_password=temp_pw,
        )
    except Exception as exc:
        print(f"USER_CREATE_FAIL | reason={exc}")
        return 2

    print("USER_CREATED")
    print(f"- user_id:      {args.user_id}")
    print(f"- display_name: {args.display_name}")
    print(f"- role:         {args.role}")
    print(f"- unit_code:    {args.unit_code}")
    print(f"- home_branch:  {args.home_branch}")
    print("")
    print("TEMP_PASSWORD_ISSUED (one-time display):")
    print(temp_pw)
    print("ACTION_REQUIRED: user must change password on first login.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
