"""
tools/run_end_of_day_snapshot.py

End-of-Day Snapshot Engine
--------------------------
Generates reconciliation-ready snapshot per date.

Outputs:
- audit_logs/eod_snapshots/eod_<date>.json
- audit_logs/eod_snapshots/eod_<date>_PRINT.txt

Each user starts at top of new print page (form feed).
"""

from __future__ import annotations

import sys
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
from typing import Dict, Any, List


REPO_ROOT = Path(__file__).resolve().parents[1]
JOURNAL_FILE = REPO_ROOT / "audit_logs" / "journal.jsonl"
OUT_DIR = REPO_ROOT / "audit_logs" / "eod_snapshots"


def load_journal() -> List[Dict[str, Any]]:
    if not JOURNAL_FILE.exists():
        print("Journal file not found:", JOURNAL_FILE)
        sys.exit(1)

    rows: List[Dict[str, Any]] = []
    with JOURNAL_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def extract_posting_date(rec: Dict[str, Any]) -> str | None:
    for key in ("posting_date", "value_date", "effective_date", "txn_date"):
        if key in rec and rec[key]:
            return str(rec[key])[:10]
    return None


def extract_user(rec: Dict[str, Any]) -> str:
    return (
        rec.get("checker_user_id")
        or rec.get("maker_user_id")
        or rec.get("user_id")
        or "UNKNOWN_USER"
    )


def run_eod(target_date: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    journal = load_journal()

    filtered: List[Dict[str, Any]] = []
    for rec in journal:
        d = extract_posting_date(rec)
        if d == target_date:
            filtered.append(rec)

    grouped = defaultdict(list)
    for rec in filtered:
        user = extract_user(rec)
        grouped[user].append(rec)

    snapshot = {
        "generated_on_utc": datetime.now(timezone.utc).isoformat(),
        "date": target_date,
        "total_records": len(filtered),
        "users": {},
    }

    for user, rows in grouped.items():
        snapshot["users"][user] = {
            "count": len(rows),
            "entries": rows,
        }

    # Write JSON snapshot
    json_out = OUT_DIR / f"eod_{target_date}.json"
    with json_out.open("w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)

    # Write PRINT file
    print_out = OUT_DIR / f"eod_{target_date}_PRINT.txt"
    with print_out.open("w", encoding="utf-8") as f:
        for idx, (user, rows) in enumerate(grouped.items()):
            if idx > 0:
                f.write("\f\n")  # page break (new print page)

            f.write(f"USER: {user}\n")
            f.write(f"DATE: {target_date}\n")
            f.write("-" * 60 + "\n")

            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

            f.write("-" * 60 + "\n")
            f.write(f"TOTAL ENTRIES: {len(rows)}\n")

        f.write("\nGRAND TOTAL ENTRIES: " + str(len(filtered)) + "\n")

    print("EOD Snapshot generated:")
    print(json_out)
    print(print_out)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python tools/run_end_of_day_snapshot.py YYYY-MM-DD")
        sys.exit(1)

    run_eod(sys.argv[1])