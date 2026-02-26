"""
tools/run_gl_print.py

General Ledger Print Engine
----------------------------
Generates GL report for:
1) DATE RANGE: from -> to
2) AS-OF: from -> as_of (inclusive)

Outputs:
- audit_logs/gl_reports/gl_range_<from>_<to>.json + _PRINT.txt
- audit_logs/gl_reports/gl_asof_<from>_<asof>.json + _PRINT.txt

Features:
- Date-range filter
- As-of filter
- Running balance per account
- Auditor-ready print format
- Timezone-aware timestamps (py3.14 safe)
"""

from __future__ import annotations

import sys
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
from decimal import Decimal
from typing import Dict, Any, List, Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
JOURNAL_FILE = REPO_ROOT / "audit_logs" / "journal.jsonl"
OUT_DIR = REPO_ROOT / "audit_logs" / "gl_reports"


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


def extract_date(rec: Dict[str, Any]) -> Optional[str]:
    for key in ("posting_date", "value_date", "effective_date", "txn_date"):
        if key in rec and rec[key]:
            return str(rec[key])[:10]
    return None


def parse_decimal(v: Any) -> Decimal:
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal("0")


def _collect_accounts(journal_rows: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    accounts = defaultdict(list)

    # Expecting entries structured with "entries": [{account, debit, credit}]
    for rec in journal_rows:
        entries = rec.get("entries") or rec.get("lines") or []
        rec_date = extract_date(rec)

        # If journal format differs, we still won’t crash.
        if not isinstance(entries, list):
            continue

        for e in entries:
            if not isinstance(e, dict):
                continue
            account = str(e.get("account") or "UNKNOWN")
            debit = parse_decimal(e.get("debit", 0))
            credit = parse_decimal(e.get("credit", 0))
            accounts[account].append({
                "date": rec_date or "UNKNOWN_DATE",
                "debit": debit,
                "credit": credit,
            })

    return accounts


def run_gl_range(date_from: str, date_to: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    journal = load_journal()

    filtered = []
    for rec in journal:
        d = extract_date(rec)
        if d and date_from <= d <= date_to:
            filtered.append(rec)

    accounts = _collect_accounts(filtered)

    report = {
        "generated_on_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "RANGE",
        "from": date_from,
        "to": date_to,
        "accounts": {},
    }

    print_lines: List[str] = []
    grand_count = 0

    for account, rows in sorted(accounts.items()):
        running = Decimal("0")
        acc_lines = []

        print_lines.append("\f")  # page break per account
        print_lines.append(f"ACCOUNT: {account}")
        print_lines.append(f"MODE: RANGE")
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
            print_lines.append(f"{r['date']} | DR {r['debit']} | CR {r['credit']} | BAL {running}")
            grand_count += 1

        report["accounts"][account] = acc_lines
        print_lines.append("-" * 60)
        print_lines.append(f"ENDING BALANCE: {running}")

    report["total_lines"] = grand_count

    json_out = OUT_DIR / f"gl_range_{date_from}_{date_to}.json"
    with json_out.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print_out = OUT_DIR / f"gl_range_{date_from}_{date_to}_PRINT.txt"
    with print_out.open("w", encoding="utf-8") as f:
        for line in print_lines:
            f.write(line + "\n")
        f.write("\nGRAND TOTAL LINES: " + str(grand_count) + "\n")

    print("GL Report generated:")
    print(json_out)
    print(print_out)


def run_gl_asof(date_from: str, as_of: str) -> None:
    """
    AS-OF mode:
    Includes all entries from date_from up to as_of inclusive.
    Produces a running balance that ends at the as-of cut.
    """
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    journal = load_journal()

    filtered = []
    for rec in journal:
        d = extract_date(rec)
        if d and date_from <= d <= as_of:
            filtered.append(rec)

    accounts = _collect_accounts(filtered)

    report = {
        "generated_on_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "AS_OF",
        "from": date_from,
        "as_of": as_of,
        "accounts": {},
    }

    print_lines: List[str] = []
    grand_count = 0

    for account, rows in sorted(accounts.items()):
        running = Decimal("0")
        acc_lines = []

        print_lines.append("\f")  # page break per account
        print_lines.append(f"ACCOUNT: {account}")
        print_lines.append(f"MODE: AS-OF")
        print_lines.append(f"FROM: {date_from}")
        print_lines.append(f"AS OF: {as_of}")
        print_lines.append("-" * 60)

        for r in sorted(rows, key=lambda x: x["date"]):
            running += r["debit"] - r["credit"]
            acc_lines.append({
                "date": r["date"],
                "debit": str(r["debit"]),
                "credit": str(r["credit"]),
                "running_balance": str(running),
            })
            print_lines.append(f"{r['date']} | DR {r['debit']} | CR {r['credit']} | BAL {running}")
            grand_count += 1

        report["accounts"][account] = acc_lines
        print_lines.append("-" * 60)
        print_lines.append(f"BALANCE AS AT {as_of}: {running}")

    report["total_lines"] = grand_count

    json_out = OUT_DIR / f"gl_asof_{date_from}_{as_of}.json"
    with json_out.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print_out = OUT_DIR / f"gl_asof_{date_from}_{as_of}_PRINT.txt"
    with print_out.open("w", encoding="utf-8") as f:
        for line in print_lines:
            f.write(line + "\n")
        f.write("\nGRAND TOTAL LINES: " + str(grand_count) + "\n")

    print("GL Report generated:")
    print(json_out)
    print(print_out)


def usage() -> None:
    print("Usage:")
    print("  RANGE: python tools/run_gl_print.py RANGE YYYY-MM-DD YYYY-MM-DD")
    print("  ASOF : python tools/run_gl_print.py ASOF  YYYY-MM-DD YYYY-MM-DD")
    print("")
    print("Examples:")
    print("  python tools/run_gl_print.py RANGE 2026-02-01 2026-02-26")
    print("  python tools/run_gl_print.py ASOF  2026-01-01 2026-02-20")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        usage()
        sys.exit(1)

    mode = sys.argv[1].strip().upper()
    a = sys.argv[2].strip()
    b = sys.argv[3].strip()

    if mode == "RANGE":
        run_gl_range(a, b)
    elif mode == "ASOF":
        run_gl_asof(a, b)
    else:
        usage()
        sys.exit(1)