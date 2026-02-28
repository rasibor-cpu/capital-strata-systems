"""
Capital Strata Systems
Institutional Trial Balance Engine – Phase 18D (COA Driven, CLI-Safe Imports)

Features:
- COA-driven account universe (institution-aware)
- Includes all COA accounts (optional zero filtering)
- Gross totals computed on journal movements
- Net balances displayed per account
- Snapshot JSON output

Journal schema (JSONL):
- execution_date (YYYY-MM-DD)
- account_no
- side: "DR" | "CR"
- amount
"""

from __future__ import annotations

import sys
import json
from pathlib import Path
from datetime import datetime
from decimal import Decimal
from typing import Dict, List

# ---------------------------------------------------------
# CLI-safe import wiring (repo-root -> sys.path)
# ---------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.ledger.coa_loader import COALoader  # noqa: E402


JOURNAL_FILE = Path("audit_logs/journal.jsonl")
SNAPSHOT_DIR = Path("audit/trial_balance_snapshots")


def parse_date(date_str: str) -> datetime:
    return datetime.strptime(str(date_str)[:10], "%Y-%m-%d")


def to_decimal(value) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def load_journal() -> List[dict]:
    if not JOURNAL_FILE.exists():
        return []

    records = []
    with JOURNAL_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except Exception:
                continue
    return records


def build_trial_balance(
    as_at: str,
    institution_type: str = "BANK",
    include_zero: bool = False,
) -> dict:

    as_at_date = parse_date(as_at)
    journals = load_journal()

    coa = COALoader(institution_type)
    coa_accounts = coa.accounts

    # Initialize gross structure for ALL COA accounts
    gross: Dict[str, Dict[str, Decimal]] = {
        acct: {"dr": Decimal("0"), "cr": Decimal("0")}
        for acct in coa_accounts.keys()
    }

    gross_total_dr = Decimal("0")
    gross_total_cr = Decimal("0")

    # Apply journal movements
    for entry in journals:
        exec_date = entry.get("execution_date")
        account = str(entry.get("account_no") or "").strip()
        side = (entry.get("side") or "").upper()
        amount = to_decimal(entry.get("amount", 0))

        if not exec_date or not account or side not in ("DR", "CR"):
            continue

        try:
            txn_date_obj = parse_date(exec_date)
        except Exception:
            continue

        if txn_date_obj > as_at_date:
            continue

        if account not in gross:
            # Journal account not in COA → governance violation (skip in TB for now)
            continue

        if side == "DR":
            gross[account]["dr"] += amount
            gross_total_dr += amount
        else:
            gross[account]["cr"] += amount
            gross_total_cr += amount

    rows = []
    net_total_dr = Decimal("0")
    net_total_cr = Decimal("0")

    for account in sorted(gross.keys()):

        meta = coa.get_account(account)
        if not meta:
            continue

        dr = gross[account]["dr"]
        cr = gross[account]["cr"]
        net = dr - cr

        if not include_zero and dr == 0 and cr == 0:
            continue

        net_dr = net if net > 0 else Decimal("0")
        net_cr = (-net) if net < 0 else Decimal("0")

        net_total_dr += net_dr
        net_total_cr += net_cr

        rows.append({
            "account_no": account,
            "account_name": meta.name,
            "account_type": meta.type,
            "net_debit": net_dr,
            "net_credit": net_cr,
            "gross_debit": dr,
            "gross_credit": cr,
        })

    return {
        "as_at": as_at,
        "institution_type": institution_type,
        "rows": rows,
        "gross_total_debit": gross_total_dr,
        "gross_total_credit": gross_total_cr,
        "net_total_debit": net_total_dr,
        "net_total_credit": net_total_cr,
        "gross_balanced": gross_total_dr == gross_total_cr,
    }


def print_trial_balance(
    as_at: str,
    institution_type: str = "BANK",
    include_zero: bool = False,
) -> dict:

    tb = build_trial_balance(as_at, institution_type, include_zero)
    rows = tb["rows"]

    print("\n" + "=" * 120)
    print("CAPITAL STRATA SYSTEMS — INSTITUTIONAL TRIAL BALANCE")
    print(f"AS AT (EXECUTION DATE): {as_at}")
    print(f"INSTITUTION TYPE: {institution_type}")
    print("=" * 120)
    print(
        f"{'ACCOUNT':<12}"
        f"{'NAME':<28}"
        f"{'TYPE':<14}"
        f"{'NET DR':>15}"
        f"{'NET CR':>15}"
        f"{'GROSS DR':>18}"
        f"{'GROSS CR':>18}"
    )
    print("-" * 120)

    for r in rows:
        print(
            f"{r['account_no']:<12}"
            f"{r['account_name']:<28}"
            f"{r['account_type']:<14}"
            f"{r['net_debit']:>15,.2f}"
            f"{r['net_credit']:>15,.2f}"
            f"{r['gross_debit']:>18,.2f}"
            f"{r['gross_credit']:>18,.2f}"
        )

    print("-" * 120)
    print(
        f"{'TOTAL (GROSS)':<69}"
        f"{tb['gross_total_debit']:>18,.2f}"
        f"{tb['gross_total_credit']:>18,.2f}"
    )
    print(
        f"{'TOTAL (NET)':<42}"
        f"{tb['net_total_debit']:>15,.2f}"
        f"{tb['net_total_credit']:>15,.2f}"
    )
    print("=" * 120)

    if tb["gross_balanced"]:
        print("✓ Trial Balance (GROSS) Balanced")
    else:
        diff = tb["gross_total_debit"] - tb["gross_total_credit"]
        print(f"⚠ WARNING: Trial Balance (GROSS) NOT balanced. Difference: {diff:,.2f}")

    return tb


def save_snapshot(tb: dict) -> None:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    as_at = tb["as_at"]
    out = SNAPSHOT_DIR / f"trial_balance_{as_at}.json"

    serializable = dict(tb)
    serializable["rows"] = [
        {
            "account_no": r["account_no"],
            "account_name": r["account_name"],
            "account_type": r["account_type"],
            "net_debit": str(r["net_debit"]),
            "net_credit": str(r["net_credit"]),
            "gross_debit": str(r["gross_debit"]),
            "gross_credit": str(r["gross_credit"]),
        }
        for r in tb["rows"]
    ]
    serializable["gross_total_debit"] = str(tb["gross_total_debit"])
    serializable["gross_total_credit"] = str(tb["gross_total_credit"])
    serializable["net_total_debit"] = str(tb["net_total_debit"])
    serializable["net_total_credit"] = str(tb["net_total_credit"])
    serializable["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with out.open("w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2)

    print(f"Snapshot saved to: {out}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python backend/app/reporting/trial_balance.py YYYY-MM-DD [BANK] [true|false]")
        raise SystemExit(1)

    as_at = sys.argv[1]
    institution_type = sys.argv[2] if len(sys.argv) > 2 else "BANK"
    include_zero = False
    if len(sys.argv) > 3:
        include_zero = sys.argv[3].lower() in ("true", "1", "yes")

    tb = print_trial_balance(as_at, institution_type, include_zero)
    save_snapshot(tb)