"""
tools/print_report.py

CSS Print Report CLI (FinCon-style control surface)
---------------------------------------------------
User controls:
- what report to print (report_id)
- timeframe (date range or ts range)
- explicit content (sections)
- sign-off identity (caller)
- authority simulation (roles/perms)

Examples:
  python tools/print_report.py --list
  python tools/print_report.py governance_summary --role ADMIN
  python tools/print_report.py governance_summary --role ADMIN --from-date 2026-02-25 --to-date 2026-02-25
  python tools/print_report.py governance_summary --role ADMIN --sections summary,top_reasons,signoff
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure repo root is on path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.reporting.report_printer import print_report, list_reports, build_caller  # noqa: E402
from engine.reporting.report_request import ReportRequest, ReportTimeframe  # noqa: E402

# Import reports so they register
import tools.analyze_governance_log  # noqa: F401,E402


def _parse_sections(s: str):
    parts = [p.strip() for p in (s or "").split(",") if p.strip()]
    return set(parts)


def main():
    p = argparse.ArgumentParser()

    p.add_argument("report_id", nargs="?", help="Report ID (use --list to see options)")
    p.add_argument("--list", action="store_true", help="List available reports")

    # Authority / identity
    p.add_argument("--user-id", default="operator", help="Caller user_id for sign-off")
    p.add_argument("--name", default="Operator", help="Caller display name for sign-off")
    p.add_argument("--role", action="append", default=[], help="Caller role (repeatable)")
    p.add_argument("--perm", action="append", default=[], help="Caller permission (repeatable)")

    # Timeframe
    p.add_argument("--from-date", dest="from_date", default=None, help="YYYY-MM-DD")
    p.add_argument("--to-date", dest="to_date", default=None, help="YYYY-MM-DD")
    p.add_argument("--from-ts", dest="from_ts", default=None, help="unix seconds")
    p.add_argument("--to-ts", dest="to_ts", default=None, help="unix seconds")

    # Explicit content
    p.add_argument("--sections", default="", help="Comma list (e.g., summary,top_reasons,correlation,sizing,signoff)")

    # Scope controls (placeholders for FinCon integration)
    p.add_argument("--scope-id", default=None)
    p.add_argument("--target-user-id", default=None)
    p.add_argument("--currency", default=None)

    # Governance log path override
    p.add_argument("--log", default="audit_logs/governance_decisions.jsonl", help="Path to governance JSONL log")

    # Output
    p.add_argument("--json", action="store_true", help="Also print JSON payload")

    args = p.parse_args()

    if args.list:
        catalog = list_reports()
        print("Available reports:")
        for rid in sorted(catalog.keys()):
            meta = catalog[rid]
            print(
                f"  - {rid} :: {meta['title']}  "
                f"roles={meta['required_roles']} "
                f"perms={meta['required_permissions']} "
                f"default_sections={meta['default_sections']}"
            )
        return

    if not args.report_id:
        raise SystemExit("Missing report_id. Try: python tools/print_report.py --list")

    caller = build_caller(
        user_id=args.user_id,
        display_name=args.name,
        roles=args.role,
        permissions=args.perm,
    )

    tf = ReportTimeframe(
        mode="range",
        start_date=args.from_date,
        end_date=args.to_date,
        start_ts=float(args.from_ts) if args.from_ts is not None else None,
        end_ts=float(args.to_ts) if args.to_ts is not None else None,
    )

    req = ReportRequest(
        report_id=args.report_id,
        caller=caller,
        timeframe=tf,
        sections=_parse_sections(args.sections),
        scope_id=args.scope_id,
        target_user_id=args.target_user_id,
        currency=args.currency,
        params={"log_path": args.log},
    )

    result = print_report(req)

    print(result.text)

    if args.json:
        print(json.dumps(result.payload, indent=2))


if __name__ == "__main__":
    main()