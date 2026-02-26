"""
tools/print_daily_journals_by_dimension.py

Daily Journal Printout grouped by a chosen dimension key.
Each group starts on a new page (\f).

Usage:
  python tools/print_daily_journals_by_dimension.py 2026-02-01 maker_user_id
  python tools/print_daily_journals_by_dimension.py 2026-02-01 dims.branch
  python tools/print_daily_journals_by_dimension.py 2026-02-01 dims.country
"""

from __future__ import annotations

import sys
import json
from pathlib import Path
from collections import defaultdict

JOURNAL_FILE = Path("audit_logs") / "journal.jsonl"
OUT_DIR = Path("audit_logs") / "prints"


def get_key(row: dict, key: str) -> str:
    if key == "maker_user_id":
        return row.get("maker_user_id") or "UNKNOWN_MAKER"
    if key == "checker_user_id":
        return row.get("checker_user_id") or "UNKNOWN_CHECKER"
    if key.startswith("dims."):
        k = key.split(".", 1)[1]
        dims = row.get("dims") or {}
        v = dims.get(k)
        return str(v) if v else f"UNKNOWN_{k.upper()}"
    return "UNKNOWN_KEY"


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: python tools/print_daily_journals_by_dimension.py YYYY-MM-DD <maker_user_id|checker_user_id|dims.branch|dims.country|...>")
        return 2

    day = sys.argv[1].strip()
    group_key = sys.argv[2].strip()

    if not JOURNAL_FILE.exists():
        print(f"Journal file not found: {JOURNAL_FILE}")
        return 1

    rows_by_group = defaultdict(list)

    with JOURNAL_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("execution_date") != day:
                continue
            g = get_key(r, group_key)
            rows_by_group[g].append(r)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"daily_journals_{day}_by_{group_key.replace('.','_')}.txt"

    groups = sorted(rows_by_group.keys())

    with out.open("w", encoding="utf-8") as w:
        w.write(f"CSS DAILY JOURNAL PRINT\nDATE: {day}\nGROUPED BY: {group_key}\n\n")
        for idx, g in enumerate(groups):
            if idx > 0:
                w.write("\f")
            w.write(f"GROUP: {g}\n")
            w.write("=" * 100 + "\n")
            w.write("journal_id | ticket_id | acct | side | amount | ccy | maker | checker | dims | created_at\n")
            w.write("-" * 100 + "\n")

            items = sorted(rows_by_group[g], key=lambda x: x.get("journal_id", ""))

            for r in items:
                w.write(
                    f"{r.get('journal_id',''):>10} | "
                    f"{r.get('ticket_id',''):>8} | "
                    f"{r.get('account_no',''):>6} | "
                    f"{r.get('side',''):>2} | "
                    f"{r.get('amount',''):>10} | "
                    f"{r.get('currency',''):>3} | "
                    f"{(r.get('maker_user_id') or ''):>10} | "
                    f"{(r.get('checker_user_id') or ''):>10} | "
                    f"{json.dumps(r.get('dims') or {}, ensure_ascii=False)} | "
                    f"{r.get('created_at','')}\n"
                )

            w.write("\nTOTAL LINES: " + str(len(items)) + "\n")

    print(f"WROTE: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())