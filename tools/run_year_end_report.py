"""
Year-End Consolidated Financial Report – Phase 14f

Usage:
  python tools/run_year_end_report.py 2026
"""

from __future__ import annotations
import sys
import json
from decimal import Decimal
from pathlib import Path
from collections import defaultdict

JOURNAL_FILE = Path("audit_logs") / "journal.jsonl"
ACCOUNT_REGISTRY = Path("backend/app/ledger/account_registry.json")
OUT_DIR = Path("audit_logs") / "year_end"


def dec(x): return Decimal(str(x))


def main():
    if len(sys.argv) < 2:
        print("Usage: python tools/run_year_end_report.py YYYY")
        return 2

    year = sys.argv[1].strip()

    registry = json.loads(ACCOUNT_REGISTRY.read_text())

    bs = defaultdict(Decimal)
    is_income = defaultdict(Decimal)
    is_expense = defaultdict(Decimal)

    with JOURNAL_FILE.open() as f:
        for line in f:
            r = json.loads(line)
            if not r["execution_date"].startswith(year):
                continue

            acct = r["account_no"]
            side = r["side"]
            amt = dec(r["amount"])
            meta = registry.get(acct)
            if not meta:
                continue

            if meta["statement"] == "INCOME_STATEMENT":
                if meta["type"] == "INCOME":
                    if side == "CR": is_income[acct] += amt
                    else: is_income[acct] -= amt
                else:
                    if side == "DR": is_expense[acct] += amt
                    else: is_expense[acct] -= amt
            else:
                if side == "DR": bs[acct] += amt
                else: bs[acct] -= amt

    total_income = sum(is_income.values())
    total_expense = sum(is_expense.values())
    net_income = total_income - total_expense

    bs["400"] += net_income  # retained earnings roll-up

    report = {
        "schema": "CSS_YEAR_END_V1",
        "year": year,
        "income_statement": {
            "income": {k: str(v) for k, v in is_income.items()},
            "expense": {k: str(v) for k, v in is_expense.items()},
            "net_income": str(net_income)
        },
        "balance_sheet": {
            "accounts": {k: str(v) for k, v in bs.items()}
        }
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"YEAR_END_{year}.json"
    out.write_text(json.dumps(report, indent=2))

    print("Year-End Report Written:", out)
    print("Net Income:", net_income)


if __name__ == "__main__":
    main()