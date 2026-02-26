"""
tools/run_gl_print.py

General Ledger Print Engine (Schema-Aligned)
--------------------------------------------
Supports:
- RANGE mode
- AS-OF mode

Journal schema (per line):
{
  journal_id,
  ticket_id,
  execution_date,
  account_no,
  side: DR | CR,
  amount,
  ...
}
"""

from __future__ import annotations

import sys
import json
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal
from collections import defaultdict
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
            try:
                rows.append(json.loads(line.strip()))
            except Exception:
                continue
    return rows


def parse_decimal(v: Any) -> Decimal:
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal("0")


def collect_accounts(rows: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    accounts = defaultdict(list)

    for r in rows:
        account = str(r.get("account_no", "UNKNOWN"))
        side = str(r.get("side", "")).upper()
        amount = parse_decimal(r.get("amount", 0))
        date = str(r.get("execution_date", ""))[:10]

        if side == "DR":
            debit = amount
            credit = Decimal("0")
        elif side == "CR":
            debit = Decimal("0")
            credit = amount
        else:
            debit = Decimal("0")
            credit = Decimal("0")

        accounts[account].append({
            "date": date,
            "debit": debit,
            "credit": credit,
        })

    return accounts


def filter_rows(journal: List[Dict[str, Any]], start: str, end: str):
    return [
        r for r in journal
        if start <= str(r.get("execution_date", ""))[:10] <= end
    ]


def generate_report(mode: str, start: str, end: str):

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    journal = load_journal()
    filtered = filter_rows(journal, start, end)
    accounts = collect_accounts(filtered)

    report = {
        "generated_on_utc": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "from": start,
        "to": end,
        "accounts": {}
    }

    print_lines = []
    total_lines = 0

    for account in sorted(accounts.keys()):
        running = Decimal("0")
        rows = sorted(accounts[account], key=lambda x: x["date"])

        print_lines.append("\f")
        print_lines.append(f"ACCOUNT: {account}")
        print_lines.append(f"MODE: {mode}")
        print_lines.append(f"PERIOD: {start} to {end}")
        print_lines.append("-" * 60)

        acc_output = []

        for r in rows:
            running += r["debit"] - r["credit"]

            acc_output.append({
                "date": r["date"],
                "debit": str(r["debit"]),
                "credit": str(r["credit"]),
                "running_balance": str(running),
            })

            print_lines.append(
                f"{r['date']} | DR {r['debit']} | CR {r['credit']} | BAL {running}"
            )

            total_lines += 1

        report["accounts"][account] = acc_output

        print_lines.append("-" * 60)
        print_lines.append(f"ENDING BALANCE: {running}")

    report["total_lines"] = total_lines

    json_out = OUT_DIR / f"gl_{mode.lower()}_{start}_{end}.json"
    print_out = OUT_DIR / f"gl_{mode.lower()}_{start}_{end}_PRINT.txt"

    with json_out.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    with print_out.open("w", encoding="utf-8") as f:
        for line in print_lines:
            f.write(line + "\n")
        f.write("\nGRAND TOTAL LINES: " + str(total_lines))

    print("GL Report generated:")
    print(json_out)
    print(print_out)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage:")
        print("  python tools/run_gl_print.py RANGE YYYY-MM-DD YYYY-MM-DD")
        print("  python tools/run_gl_print.py ASOF YYYY-MM-DD YYYY-MM-DD")
        sys.exit(1)

    mode = sys.argv[1].upper()
    start = sys.argv[2]
    end = sys.argv[3]

    if mode not in ("RANGE", "ASOF"):
        print("Mode must be RANGE or ASOF")
        sys.exit(1)

    generate_report(mode, start, end)