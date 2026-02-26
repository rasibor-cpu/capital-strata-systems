"""
Year-End Consolidated Financial Report – Phase 17C (Governance Hardened)
Capital Strata Systems

What this does:
- Aggregates journal entries for YYYY
- Builds Income Statement
- Rolls Net Income into Retained Earnings (account 400)
- Writes year-end snapshot JSON
- Records YEAR_END close event (idempotent)
- Attaches schema_version + integrity hash + deterministic report_id
- Attaches lineage metadata from CloseRegistry

Usage:
  python tools/run_year_end_report.py 2026 --role SUPER_USER
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
# Ensure repo root is importable
# ------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.posting.close_registry import CloseRegistry
from engine.reporting.report_integrity import attach_integrity_metadata


JOURNAL_FILE = REPO_ROOT / "audit_logs" / "journal.jsonl"
ACCOUNT_REGISTRY = REPO_ROOT / "backend" / "app" / "ledger" / "account_registry.json"
OUT_DIR = REPO_ROOT / "audit_logs" / "year_end"


def dec(x) -> Decimal:
    return Decimal(str(x))


def _load_registry() -> Dict[str, Any]:
    return json.loads(ACCOUNT_REGISTRY.read_text(encoding="utf-8"))


def _read_year_slice(year: str) -> list[Dict[str, Any]]:
    rows: list[Dict[str, Any]] = []
    if not JOURNAL_FILE.exists():
        return rows

    with JOURNAL_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if not str(r.get("execution_date", "")).startswith(year):
                continue
            rows.append(r)

    return rows


def build_year_end_snapshot(year: str) -> Dict[str, Any]:
    registry = _load_registry()
    year_rows = _read_year_slice(year)

    bs = defaultdict(Decimal)
    is_income = defaultdict(Decimal)
    is_expense = defaultdict(Decimal)

    for r in year_rows:
        acct = str(r.get("account_no", "")).strip()
        side = str(r.get("side", "")).strip().upper()
        amt = dec(r.get("amount", "0"))

        meta = registry.get(acct)
        if not meta:
            continue

        if meta.get("statement") == "INCOME_STATEMENT":
            if meta.get("type") == "INCOME":
                if side == "CR":
                    is_income[acct] += amt
                else:
                    is_income[acct] -= amt
            else:
                if side == "DR":
                    is_expense[acct] += amt
                else:
                    is_expense[acct] -= amt
        else:
            if side == "DR":
                bs[acct] += amt
            else:
                bs[acct] -= amt

    total_income = sum(is_income.values())
    total_expense = sum(is_expense.values())
    net_income = total_income - total_expense

    # Roll to retained earnings
    bs["400"] += net_income

    report = {
        "year": year,
        "counts": {"journal_rows_scanned": len(year_rows)},
        "income_statement": {
            "income": {k: str(v) for k, v in is_income.items()},
            "expense": {k: str(v) for k, v in is_expense.items()},
            "net_income": str(net_income),
            "total_income": str(total_income),
            "total_expense": str(total_expense),
        },
        "balance_sheet": {
            "accounts": {k: str(v) for k, v in bs.items()}
        },
    }

    return attach_integrity_metadata(
        report,
        schema_name="CSS_YEAR_END_V1",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("year", help="YYYY (e.g., 2026)")
    parser.add_argument("--role", default="SUPER_USER")
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    year = args.year.strip()
    role = args.role.strip().upper()

    try:
        y = int(year)
    except Exception:
        print("Invalid year format. Use YYYY.")
        return 2

    # Record close event (idempotent)
    close_result = CloseRegistry.record_close(
        close_type="YEAR_END",
        year=y,
        month=None,
        actor_role=role,
        notes=args.notes,
    )

    status = close_result.get("status", "UNKNOWN")

    # Build report
    snapshot = build_year_end_snapshot(year)

    # Attach lineage (latest close event reference)
    latest_close = CloseRegistry.latest_close()
    if latest_close:
        snapshot["lineage"] = {
            "latest_close_event": latest_close
        }

    # Persist
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"YEAR_END_{year}.json"
    out.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")

    print("Year-End Close Status:", status)
    print("Year-End Report Written:", out)
    print("Net Income:", snapshot["income_statement"]["net_income"])
    print("Schema Version:", snapshot.get("schema_version"))
    print("Report ID:", snapshot.get("report_id"))
    print("Integrity Hash:", snapshot.get("integrity", {}).get("hash"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())