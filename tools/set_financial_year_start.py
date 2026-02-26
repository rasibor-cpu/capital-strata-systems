"""
Set Financial Year Start (Super User / Admin)
Capital Strata Systems – Phase 18A

Usage:
  python tools/set_financial_year_start.py --month 4 --day 1 --role SUPER_USER --notes "FY starts Apr 1"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.fiscal.fiscal_calendar import FiscalCalendar


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--month", type=int, required=True)
    p.add_argument("--day", type=int, required=True)
    p.add_argument("--role", default="SUPER_USER")
    p.add_argument("--notes", default="")
    args = p.parse_args()

    cfg = FiscalCalendar.set_fy_start(args.month, args.day, role=args.role, notes=args.notes)
    fy = FiscalCalendar.get_active_fy()

    print("FY Start Set:", cfg["fy_start_month"], cfg["fy_start_day"])
    print("Active FY:", fy.fy_label, fy.start_date.isoformat(), "→", fy.end_date.isoformat())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())