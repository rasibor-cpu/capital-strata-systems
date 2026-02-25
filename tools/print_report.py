"""
tools/print_report.py

CSS Print Report CLI (Dev Harness)
----------------------------------
Canonical dev entrypoint to reproduce reports on demand.

USAGE (Windows):
  python tools/print_report.py --list
  python tools/print_report.py governance_summary --role ADMIN
  python tools/print_report.py governance_summary --role FINCON_REPORTING
  python tools/print_report.py governance_summary --role USER   (should block)

Note:
- In production, the FinCon Journal "Print" workflow will call engine.reporting.report_printer.print_report()
  with real roles/permissions. This CLI is a harness that simulates those.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure REPO_ROOT is on sys.path so `import engine.*` works reliably
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.reporting.report_printer import print_report, list_reports  # noqa: E402

# Import report modules so they register themselves
# (Add more imports here as more reports are created.)
import tools.analyze_governance_log  # noqa: F401,E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("report_id", nargs="?", help="Report ID (use --list to see options)")
    p.add_argument("--list", action="store_true", help="List available reports")
    p.add_argument("--log", default="audit_logs/governance_decisions.jsonl", help="Path to governance JSONL log")
    p.add_argument("--json", action="store_true", help="Also print JSON payload")
    p.add_argument("--role", action="append", default=[], help="Simulated user role (repeatable)")
    p.add_argument("--perm", action="append", default=[], help="Simulated user permission (repeatable)")
    args = p.parse_args()

    if args.list:
        catalog = list_reports()
        print("Available reports:")
        for rid in sorted(catalog.keys()):
            meta = catalog[rid]
            print(f"  - {rid} :: {meta['title']}  roles={meta['required_roles']} perms={meta['required_permissions']}")
        return

    if not args.report_id:
        raise SystemExit("Missing report_id. Try: python tools/print_report.py --list")

    kwargs = {}
    if args.report_id == "governance_summary":
        kwargs["log_path"] = args.log

    result = print_report(
        args.report_id,
        user_roles=args.role,
        user_permissions=args.perm,
        **kwargs,
    )

    print(result.text)
    if args.json:
        print(json.dumps(result.payload, indent=2))


if __name__ == "__main__":
    main()