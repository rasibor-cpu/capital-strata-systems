"""
Month-End Close Engine – Phase 14e
Capital Strata Systems

- Aggregates journal entries for YYYY-MM
- Builds Income Statement
- Transfers Net Income to Retained Earnings (account 400)
- Produces month-end snapshot JSON

Usage:
  python tools/run_month_end_close.py 2026-02
"""

from __future__ import annotations
import sys
import json
import hashlib
from decimal import Decimal
from pathlib import Path
from collections import defaultdict

JOURNAL_FILE = Path("audit_logs") / "journal.jsonl"
ACCOUNT_REGISTRY = Path("backend/app/ledger/account_registry.json")
OUT_DIR = Path("audit_logs") / "month_end"


def dec(x): return Decimal(str(x))


def stable_hash(obj):
    s = json.dumps(obj, sort_keys=True)
    return hashlib.sha256(s.encode()).hexdigest()


def main():
    if len(sys.argv) < 2:
        print("Usage: python tools/run_month_end_close.py YYYY-MM")
        return 2

    month = sys.argv[1].strip()

    registry = json.loads(ACCOUNT_REGISTRY.read_text())

    income_totals = defaultdict(Decimal)
    expense_totals = defaultdict(Decimal)
    bs_totals = defaultdict(Decimal)

    with JOURNAL_FILE.open() as f:
        for line in f:
            r = json.loads(line)
            if not r["execution_date"].startswith(month):
                continue

            acct = r["account_no"]
            side = r["side"]
            amt = dec(r["amount"])

            acct_meta = registry.get(acct)
            if not acct_meta:
                continue

            if acct_meta["statement"] == "INCOME_STATEMENT":
                if acct_meta["type"] == "INCOME":
                    if side == "CR": income_totals[acct] += amt
                    else: income_totals[acct] -= amt
                elif acct_meta["type"] == "EXPENSE":
                    if side == "DR": expense_totals[acct] += amt
                    else: expense_totals[acct] -= amt
            else:
                if side == "DR": bs_totals[acct] += amt
                else: bs_totals[acct] -= amt

    total_income = sum(income_totals.values())
    total_expense = sum(expense_totals.values())
    net_income = total_income - total_expense

    # Transfer to retained earnings (400)
    bs_totals["400"] += net_income

    snapshot = {
        "schema": "CSS_MONTH_END_V1",
        "month": month,
        "income_statement": {
            "income": {k: str(v) for k, v in income_totals.items()},
            "expense": {k: str(v) for k, v in expense_totals.items()},
            "net_income": str(net_income)
        },
        "balance_sheet": {
            "accounts": {k: str(v) for k, v in bs_totals.items()}
        }
    }

    snapshot["integrity_hash"] = stable_hash(snapshot)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"MONTH_END_{month}.json"
    out.write_text(json.dumps(snapshot, indent=2))

    print("Month-End Snapshot Written:", out)
    print("Net Income:", net_income)
    print("Integrity Hash:", snapshot["integrity_hash"])


if __name__ == "__main__":
    main()