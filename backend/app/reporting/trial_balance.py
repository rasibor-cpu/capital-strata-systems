"""
Capital Strata Systems
Institutional Trial Balance Engine – Phase 17 (JSONL-Compatible)

Features:
- Reads append-only journal.jsonl (log structured)
- As-at transaction date filter
- Net debit / credit presentation
- Zero-balance toggle
- Snapshot persistence
- Graceful record skipping (no crash on bad row)

Journal expected at:
    audit_logs/journal.jsonl
"""

from __future__ import annotations

import sys
import json
from pathlib import Path
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Tuple


# =============================
# CONFIGURATION
# =============================

JOURNAL_FILE = Path("audit_logs/journal.jsonl")
SNAPSHOT_DIR = Path("audit/trial_balance_snapshots")


# =============================
# UTILITIES
# =============================

def parse_date(date_str: str) -> datetime:
    return datetime.strptime(date_str[:10], "%Y-%m-%d")


def to_decimal(value) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


# =============================
# JOURNAL LOADER (JSONL)
# =============================

def load_journal() -> List[dict]:
    if not JOURNAL_FILE.exists():
        raise FileNotFoundError(f"Journal file not found: {JOURNAL_FILE}")

    records = []
    with JOURNAL_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except Exception:
                # skip malformed rows silently
                continue

    return records


# =============================
# TRIAL BALANCE BUILDER
# =============================

def build_trial_balance(as_at: str, include_zero: bool = False) -> Tuple[List[dict], Decimal, Decimal]:
    as_at_date = parse_date(as_at)
    journals = load_journal()

    balances: Dict[str, Dict[str, Decimal]] = {}

    for entry in journals:

        txn_date = entry.get("transaction_date") or entry.get("date")
        gl_code = entry.get("gl_code") or entry.get("account_code")

        if not txn_date or not gl_code:
            continue

        try:
            txn_date_obj = parse_date(str(txn_date))
        except Exception:
            continue

        if txn_date_obj > as_at_date:
            continue

        debit = to_decimal(entry.get("debit", 0))
        credit = to_decimal(entry.get("credit", 0))

        if gl_code not in balances:
            balances[gl_code] = {"debit": Decimal("0"), "credit": Decimal("0")}

        balances[gl_code]["debit"] += debit
        balances[gl_code]["credit"] += credit

    trial_balance_rows = []
    total_debit = Decimal("0")
    total_credit = Decimal("0")

    for gl_code in sorted(balances.keys()):
        total_dr = balances[gl_code]["debit"]
        total_cr = balances[gl_code]["credit"]
        net = total_dr - total_cr

        if not include_zero and net == 0:
            continue

        debit_col = net if net > 0 else Decimal("0")
        credit_col = (-net) if net < 0 else Decimal("0")

        total_debit += debit_col
        total_credit += credit_col

        trial_balance_rows.append({
            "gl_code": gl_code,
            "debit": debit_col,
            "credit": credit_col
        })

    return trial_balance_rows, total_debit, total_credit


# =============================
# PRINT ENGINE
# =============================

def print_trial_balance(as_at: str, include_zero: bool = False):
    rows, total_debit, total_credit = build_trial_balance(as_at, include_zero)

    print("\n" + "=" * 80)
    print("CAPITAL STRATA SYSTEMS — TRIAL BALANCE")
    print(f"AS AT (TRANSACTION DATE): {as_at}")
    print("=" * 80)
    print(f"{'GL CODE':<30}{'DEBIT':>25}{'CREDIT':>25}")
    print("-" * 80)

    for row in rows:
        print(f"{row['gl_code']:<30}{row['debit']:>25,.2f}{row['credit']:>25,.2f}")

    print("-" * 80)
    print(f"{'TOTAL':<30}{total_debit:>25,.2f}{total_credit:>25,.2f}")
    print("=" * 80)

    if total_debit != total_credit:
        diff = total_debit - total_credit
        print(f"⚠ WARNING: NOT BALANCED. Difference: {diff:,.2f}")
    else:
        print("✓ Trial Balance Balanced")


# =============================
# SNAPSHOT STORAGE
# =============================

def save_snapshot(as_at: str, include_zero: bool = False):
    rows, total_debit, total_credit = build_trial_balance(as_at, include_zero)

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    snapshot_file = SNAPSHOT_DIR / f"trial_balance_{as_at}.json"

    with snapshot_file.open("w", encoding="utf-8") as f:
        json.dump({
            "as_at": as_at,
            "rows": [
                {
                    "gl_code": r["gl_code"],
                    "debit": str(r["debit"]),
                    "credit": str(r["credit"])
                }
                for r in rows
            ],
            "total_debit": str(total_debit),
            "total_credit": str(total_credit),
            "balanced": total_debit == total_credit,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }, f, indent=4)

    print(f"Snapshot saved to: {snapshot_file}")


# =============================
# ENTRY POINT
# =============================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("python backend/app/reporting/trial_balance.py YYYY-MM-DD [true|false]")
        sys.exit(1)

    as_at = sys.argv[1]
    include_zero_flag = False

    if len(sys.argv) > 2:
        include_zero_flag = sys.argv[2].lower() in ("true", "1", "yes")

    print_trial_balance(as_at, include_zero_flag)
    save_snapshot(as_at, include_zero_flag)