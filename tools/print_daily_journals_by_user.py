"""
tools/print_daily_journals_by_user.py

Daily Journal Printout (Batch Review)
- Reads audit_logs/journal.jsonl
- Filters by execution_date
- Groups by maker_user_id (fallback: UNKNOWN)
- Writes a single text report with page breaks (\f) so each user starts new page

Usage:
  python tools/print_daily_journals_by_user.py 2026-02-01
"""

from __future__ import annotations

import sys
import json
from pathlib import Path
from collections import defaultdict

JOURNAL_FILE = Path("audit_logs") / "journal.jsonl"
OUT_DIR = Path("audit_logs") / "prints"


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python tools/print_daily_journals_by_user.py YYYY-MM-DD")
        return 2

    day = sys.argv[1].strip()
    if not JOURNAL_FILE.exists():
        print(f"Journal file not found: {JOURNAL_FILE}")
        return 1

    rows_by_user = defaultdict(list)

    with JOURNAL_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)

            # Filter by business date
            if r.get("execution_date") != day:
                continue

            user = r.get("maker_user_id") or "UNKNOWN_MAKER"
            rows_by_user[user].append(r)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"daily_journals_{day}.txt"

    # Sort users for stable print
    users = sorted(rows_by_user.keys())

    with out.open("w", encoding="utf-8") as w:
        w.write(f"CSS DAILY JOURNAL PRINT\nDATE: {day}\n\n")
        for idx, user in enumerate(users):
            if idx > 0:
                w.write("\f")  # form feed = new page in many print workflows

            w.write(f"USER: {user}\n")
            w.write("=" * 80 + "\n")
            w.write("journal_id | ticket_id | acct | side | amount | ccy | checker | created_at\n")
            w.write("-" * 80 + "\n")

            # Stable sort by journal_id
            items = sorted(rows_by_user[user], key=lambda x: x.get("journal_id", ""))

            for r in items:
                w.write(
                    f"{r.get('journal_id',''):>10} | "
                    f"{r.get('ticket_id',''):>8} | "
                    f"{r.get('account_no',''):>6} | "
                    f"{r.get('side',''):>2} | "
                    f"{r.get('amount',''):>10} | "
                    f"{r.get('currency',''):>3} | "
                    f"{(r.get('checker_user_id') or ''):>10} | "
                    f"{r.get('created_at','')}\n"
                )

            w.write("\nTOTAL LINES: " + str(len(items)) + "\n")

    print(f"WROTE: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())