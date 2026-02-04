# ops/create_user.py
# Usage:
#   python ops\create_user.py <user_id> "<display_name>" <role> <unit_code> <home_branch> [temp_password]
#
# Example:
#   python ops\create_user.py 1369 "Robert Asibor" super_user CORE main CHANGE_ME_NOW_1369
#
# Notes:
# - temp_password is REQUIRED by the underlying create_user() API.
# - If omitted, we auto-generate a temp password and print it ONCE.

from __future__ import annotations

import argparse
import secrets
import string
import sys

from backend.app.security.user_registry import create_user


def _gen_temp_password(length: int = 14) -> str:
    alphabet = string.ascii_uppercase + string.ascii_lowercase + string.digits
    # Avoid punctuation to reduce shell/typing issues
    return "".join(secrets.choice(alphabet) for _ in range(length))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("user_id", type=int)
    p.add_argument("display_name", type=str)
    p.add_argument("role", type=str)       # e.g. super_user, admin, operator
    p.add_argument("unit_code", type=str)  # e.g. CORE, TRADING, OPS, RISK
    p.add_argument("home_branch", type=str)
    p.add_argument("temp_password", nargs="?", default=None)

    args = p.parse_args()

    temp_pw = args.temp_password or _gen_temp_password()

    try:
        create_user(
            user_id=args.user_id,
            display_name=args.display_name,
            role=args.role,
            unit_code=args.unit_code,
            home_branch=args.home_branch,
            temp_password=temp_pw,   # ✅ FIX: pass required argument
        )
    except Exception as e:
        print(f"USER_CREATE_FAIL | reason={e}")
        return 2

    print("USER_CREATED")
    print(f"- user_id:       {args.user_id}")
    print(f"- display_name:  {args.display_name}")
    print(f"- role:          {args.role}")
    print(f"- unit_code:     {args.unit_code}")
    print(f"- home_branch:   {args.home_branch}")
    print("")
    print("TEMP_PASSWORD_ISSUED (one-time display):")
    print(temp_pw)
    print("ACTION_REQUIRED: user must change password on first login.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
