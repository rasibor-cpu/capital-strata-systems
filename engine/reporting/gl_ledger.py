"""
GL Ledger Reporting – Phase 1 Control Layer
Capital Strata Systems

Supports:
- gl_print (date range + running balance)
- gl_as_of  (position as of date)

Data source:
- audit_logs/journal.jsonl (repo-root)
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional


REPO_ROOT = Path(__file__).resolve().parents[2]
JOURNAL_FILE = REPO_ROOT / "audit_logs" / "journal.jsonl"


# ---------------------------------------------------------
# Utilities
# ---------------------------------------------------------

def _parse_date(d: Optional[str]) -> Optional[datetime]:
    if not d:
        return None
    return datetime.strptime(d, "%Y-%m-%d")


def _load_journal() -> List[Dict[str, Any]]:
    if not JOURNAL_FILE.exists():
        return []

    rows: List[Dict[str, Any]] = []
    with JOURNAL_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def _extract_lines(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Compatible with your journal structure.
    Supports both:
    - flat entry
    - nested under 'entry'
    """
    entry = record.get("entry") or record

    if isinstance(entry, dict) and "account_no" in entry:
        return [entry]

    if isinstance(entry, dict) and "lines" in entry:
        return entry["lines"]

    return []


# ---------------------------------------------------------
# Core Engine
# ---------------------------------------------------------

def generate_gl_print(
    *,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    as_of_date: Optional[str] = None,
    role: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    filters = filters or {}
    account_filter = filters.get("account_no")
    currency_filter = filters.get("currency")

    start = _parse_date(from_date)
    end = _parse_date(to_date)

    rows = _load_journal()

    ledger: List[Dict[str, Any]] = []
    balance = 0.0

    for record in rows:
        lines = _extract_lines(record)

        for ln in lines:

            acc = str(ln.get("account_no"))
            ccy = ln.get("currency")
            exec_date = ln.get("execution_date")

            if account_filter and acc != account_filter:
                continue

            if currency_filter and ccy != currency_filter:
                continue

            if exec_date:
                dt = _parse_date(exec_date)
                if start and dt < start:
                    continue
                if end and dt > end:
                    continue

            amount = float(ln.get("amount", 0))
            side = ln.get("side", "").upper()

            if side == "DR":
                balance += amount
            elif side == "CR":
                balance -= amount

            ledger.append({
                "execution_date": exec_date,
                "account_no": acc,
                "side": side,
                "amount": amount,
                "running_balance": round(balance, 2),
                "currency": ccy,
                "journal_id": ln.get("journal_id"),
            })

    return {
        "type": "GL_LEDGER",
        "from_date": from_date,
        "to_date": to_date,
        "account_no": account_filter,
        "currency": currency_filter,
        "rows": ledger,
        "final_balance": round(balance, 2),
    }


def generate_gl_as_of(
    *,
    as_of_date: str,
    role: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    result = generate_gl_print(
        from_date=None,
        to_date=as_of_date,
        filters=filters,
    )

    return {
        "type": "GL_AS_OF",
        "as_of_date": as_of_date,
        "account_no": result.get("account_no"),
        "balance": result.get("final_balance"),
    }