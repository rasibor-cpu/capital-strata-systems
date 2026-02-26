"""
tools/run_gl_print.py

General Ledger Print Engine
----------------------------
Generates GL report for a given date range.

Outputs:
- audit_logs/gl_reports/gl_<from>_<to>.json
- audit_logs/gl_reports/gl_<from>_<to>_PRINT.txt

Features:
- Date-range filter
- Running balance per account
- Auditor-ready print format
"""

from __future__ import annotations

import sys
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from decimal import Decimal
from typing import Dict, Any, List


REPO_ROOT = Path(__file__).resolve().parents[1]
JOURNAL_FILE = REPO_ROOT / "audit_logs" / "journal.jsonl"
OUT_DIR = REPO_ROOT / "audit_logs" / "gl_reports"


def load_journal() -> List[Dict[str, Any]]:
    if not JOURNAL_FILE.exists():
        print("Journal file not found:", JOURNAL_FILE)
        sys.exit(1)

    rows = []
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


def extract_date(rec: Dict[str, Any]) -> str | None:
    for key in ("posting_date", "value_date", "effective_date", "txn_date"):
        if key in rec and rec[key]:
            return str(rec[key])[:10]
    return None


def parse_decimal(v: Any) -> Decimal:
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal("0")


def run_gl_print(date_from: str, date_to: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    journal = load_journal()

    filtered = []
    for rec in journal:
        d = extract_date(rec)
        if d and date_from <= d <= date_to:
            filtered.append(rec)

    accounts = defaultdict(list)

    # Expecting entries structured with "entries": [{account, debit, credit}]
    for rec in filtered:
        entries = rec.get("entries") or rec.get("lines") or []
        rec_date = extract_date(rec)

        for e in entries:
            account = str(e.get("account") or "UNKNOWN")
            debit = parse_decimal(e.get("debit", 0))
            credit = parse_decimal(e.get("credit", 0))
            accounts[account].append({
                "date": rec_date,
                "debit": debit,
                "credit": credit,
                "raw": e,
            })

    report = {
        "generated_on": datetime.utcnow().isoformat(),
        "from": date_from,
        "to": date_to,
        "accounts": {},
    }

    print_lines = []

    for account, rows in sorted(accounts.items()):
        running = Decimal("0")
        acc_lines = []

        print_lines.append("\f")  # page break per account
        print_lines.append(f"ACCOUNT: {account}")
        print_lines.append(f"PERIOD: {date_from} to {date_to}")
        print_lines.append("-" * 60)

        for r in sorted(rows, key=lambda x: x["date"]):
            running += r["debit"] - r["credit"]
            acc_lines.append({
                "date": r["date"],
                "debit": str(r["debit"]),
                "credit": str(r["credit"]),
                "running_balance": str(running),
            })

            print_lines.append(
                f"{r['date']} | DR {r['debit']} | CR {r['credit']} | BAL {running}"
            )

        report["accounts"][account] = acc_lines
        print_lines.append("-" * 60)
        print_lines.append(f"ENDING BALANCE: {running}")

    json_out = OUT_DIR / f"gl_{date_from}_{date_to}.json"
    with json_out.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print_out = OUT_DIR / f"gl_{date_from}_{date_to}_PRINT.txt"
    with print_out.open("w", encoding="utf-8") as f:
        for line in print_lines:
            f.write(line + "\n")

    print("GL Report generated:")
    print(json_out)
    print(print_out)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python tools/run_gl_print.py YYYY-MM-DD YYYY-MM-DD")
        sys.exit(1)

    run_gl_print(sys.argv[1], sys.argv[2])