"""
CLI P&L Checker – REA Capital Trading Engine

Default:
  python tools/pnl_check.py

Show details + cumulative:
  python tools/pnl_check.py --details

Custom period:
  python tools/pnl_check.py --from 2026-02-01T00:00:00+00:00 --to 2026-02-08T00:00:00+00:00 --details

Notes:
- Uses UTC ISO timestamps.
- End is exclusive.
"""

import argparse

from engine.reporting.pnl_report import (
    today, wtd, mtd, ytd,
    custom_range,
    print_summary,
    print_transaction_details,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="start", help="Start ISO timestamp (UTC recommended)")
    parser.add_argument("--to", dest="end", help="End ISO timestamp (UTC recommended, exclusive)")
    parser.add_argument("--details", action="store_true", help="Print transaction details + cumulative P&L")
    parser.add_argument("--period", choices=["today", "wtd", "mtd", "ytd"], help="Print a single named period only")

    args = parser.parse_args()

    if args.start and args.end:
        s, events = custom_range(args.start, args.end)
        print_summary(s)
        if args.details:
            print_transaction_details(events)
        return

    if args.period:
        if args.period == "today":
            s, events = today()
        elif args.period == "wtd":
            s, events = wtd()
        elif args.period == "mtd":
            s, events = mtd()
        else:
            s, events = ytd()

        print_summary(s)
        if args.details:
            print_transaction_details(events)
        return

    # Default: all rollups (summaries only)
    s, _ = today()
    print_summary(s)

    s, _ = wtd()
    print_summary(s)

    s, _ = mtd()
    print_summary(s)

    s, _ = ytd()
    print_summary(s)


if __name__ == "__main__":
    main()
