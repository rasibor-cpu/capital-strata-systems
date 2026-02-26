"""
Month-End Close Engine – Phase 17B (Governance Hardened)
Capital Strata Systems

Usage:
  python tools/run_month_end_close.py 2026-02 --role SUPER_USER
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path
from collections import defaultdict
from typing import Any, Dict

# ------------------------------------------------------------
# Ensure repo root is importable (so `engine.*` imports work)
# ------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.posting.close_registry import CloseRegistry
from engine.reporting.report_integrity import attach_integrity_metadata


JOURNAL_FILE = REPO_ROOT / "audit_logs" / "journal.jsonl"
ACCOUNT_REGISTRY = REPO_ROOT / "backend" / "app" / "ledger" / "account_registry.json"
OUT_DIR = REPO_ROOT / "audit_logs" / "month_end"


def dec(x) -> Decimal:
    return Decimal(str(x))


def _load_registry() -> Dict[str, Any]:
    return json.loads(ACCOUNT_REGISTRY.read_text(encoding="utf-8"))


def _read_month_slice(month: str) -> list[Dict[str, Any]]:
    rows: list[Dict[str, Any]] = []
    if not JOURNAL_FILE.exists():
        return rows

    with JOURNAL_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if not str(r.get("execution_date", "")).startswith(month):
                continue
            rows.append(r)
    return rows


def build_month_end_snapshot(month: str) -> Dict[str, Any]:
    registry = _load_registry()
    month_rows = _read_month_slice(month)

    income_totals = defaultdict(Decimal)
    expense_totals = defaultdict(Decimal)
    bs_totals = defaultdict(Decimal)

    for r in month_rows:
        acct = str(r.get("account_no", "")).strip()
        side = str(r.get("side", "")).strip().upper()
        amt = dec(r.get("amount", "0"))

        acct_meta = registry.get(acct)
        if not acct_meta:
            continue

        if acct_meta.get("statement") == "INCOME_STATEMENT":
            if acct_meta.get("type") == "INCOME":
                if side == "CR":
                    income_totals[acct] += amt
                else:
                    income_totals[acct] -= amt
            elif acct_meta.get("type") == "EXPENSE":
                if side == "DR":
                    expense_totals[acct] += amt
                else:
                    expense_totals[acct] -= amt
        else:
            if side == "DR":
                bs_totals[acct] += amt
            else:
                bs_totals[acct] -= amt

    total_income = sum(income_totals.values())
    total_expense = sum(expense_totals.values())
    net_income = total_income - total_expense

    # Transfer net income to retained earnings (account 400)
    bs_totals["400"] += net_income

    snapshot = {
        "schema": "CSS_MONTH_END_V1",
        "month": month,
        "counts": {"journal_rows_scanned": len(month_rows)},
        "income_statement": {
            "income": {k: str(v) for k, v in income_totals.items()},
            "expense": {k: str(v) for k, v in expense_totals.items()},
            "net_income": str(net_income),
            "total_income": str(total_income),
            "total_expense": str(total_expense),
        },
        "balance_sheet": {"accounts": {k: str(v) for k, v in bs_totals.items()}},
    }

    return attach_integrity_metadata(
    snapshot,
    schema_name="CSS_MONTH_END_V1",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("month", help="YYYY-MM (e.g., 2026-02)")
    parser.add_argument("--role", default="SUPER_USER", help="ADMIN | SUPER_USER | FINCON_REPORTING")
    parser.add_argument("--notes", default="", help="Optional close notes")
    args = parser.parse_args()

    month = args.month.strip()
    role = args.role.strip().upper()

    # Parse year/month
    try:
        year_s, month_s = month.split("-")
        year = int(year_s)
        m = int(month_s)
        if m < 1 or m > 12:
            raise ValueError()
    except Exception:
        print("Invalid month. Use YYYY-MM (e.g., 2026-02)")
        return 2

    # Record close event (idempotent)
    close_result = CloseRegistry.record_close(
        close_type="MONTH_END",
        year=year,
        month=m,
        actor_role=role,
        notes=args.notes,
    )
    status = close_result.get("status", "UNKNOWN")

    # Build + persist snapshot
    snapshot = build_month_end_snapshot(month)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"MONTH_END_{month}.json"
    out.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")

    print("Month-End Close Status:", status)
    print("Month-End Snapshot Written:", out)
    print("Net Income:", snapshot["income_statement"]["net_income"])
    print("Schema Version:", snapshot.get("schema_version"))
    print("Integrity Hash:", snapshot.get("integrity", {}).get("hash"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())