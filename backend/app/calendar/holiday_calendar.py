# ops/add_holiday.py
# Interactive admin tool: add an unscheduled holiday (global or branch-scoped)
#
# Usage:
#   python ops\add_holiday.py 2026-02-17 "Ad hoc closure" --branch main
#   python ops\add_holiday.py 2026-02-17 "Global closure"
#
# Requires login via auth_gate; role must be admin/super_user/superuser.

from __future__ import annotations

import argparse
import os
import sys

# Bind repo root for backend imports (same pattern as other ops tools)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.security.auth_gate import await_login_ready_state
from backend.app.calendar.holiday_calendar import add_unscheduled_holiday


ALLOWED_ROLES = {"admin", "super_user", "superuser", "super-user", "super user"}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("date", type=str, help="YYYY-MM-DD")
    p.add_argument("name", type=str, help="Holiday name/description")
    p.add_argument("--branch", type=str, default=None, help="Branch scope (optional). If omitted -> global.")
    args = p.parse_args()

    ctx = await_login_ready_state()
    role = str(ctx.get("role", "")).lower()
    if role not in ALLOWED_ROLES:
        print("DENIED: admin/super user required.")
        return 3

    add_unscheduled_holiday(args.date, args.name, branch=args.branch)
    scope = "global" if args.branch is None else f"branch:{args.branch}"
    print("HOLIDAY_ADDED")
    print(f"- date: {args.date}")
    print(f"- name: {args.name}")
    print(f"- scope: {scope}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
