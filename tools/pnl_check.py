"""
CLI P&L Checker – REA Capital Trading Engine (V1)

Examples:
  python -m tools.pnl_check --period today --mode TEST --details
  python -m tools.pnl_check --period today --mode LIVE --details
  python -m tools.pnl_check --from 2026-02-01T00:00:00+00:00 --to 2026-02-08T00:00:00+00:00 --mode TEST --details
"""

import argparse

from engine.reporting.pnl_report import (
    today, wtd, mtd, ytd,
    custom_range,
    print_summary,
    print_transaction_details,
)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--from", dest="start", help="Start ISO timestamp (UTC recommended)")
    p.add_argument("--to", dest="end", help="End ISO timestamp (UTC recommended, exclusive)")
    p.add_argument("--details", action="store_true", help="Print transaction details + cumulative P&L")
    p.add_argument("--period", choices=["today", "wtd", "mtd", "ytd"], help="Print a single named period only")
    p.add_argument("--mode", choices=["TEST", "LIVE"], default="TEST", help="Select ledger mode (separate files)")

    args = p.parse_args()

    if args.start and args.end:
        s, events = custom_range(args.start, args.end, mode=args.mode)
        print_summary(s)
        if args.details:
            print_transaction_details(events)
        return

    if args.period:
        if args.period == "today":
            s, events = today(mode=args.mode)
        elif args.period == "wtd":
            s, events = wtd(mode=args.mode)
        elif args.period == "mtd":
            s, events = mtd(mode=args.mode)
        else:
            s, events = ytd(mode=args.mode)

        print_summary(s)
        if args.details:
            print_transaction_details(events)
        return

    # Default: show all rollups (summaries)
    s, _ = today(mode=args.mode)
    print_summary(s)

    s, _ = wtd(mode=args.mode)
    print_summary(s)

    s, _ = mtd(mode=args.mode)
    print_summary(s)

    s, _ = ytd(mode=args.mode)
    print_summary(s)


if __name__ == "__main__":
    main()
