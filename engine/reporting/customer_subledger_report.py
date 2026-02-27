"""
Customer Subledger Report – Phase 1C (Customer Acct Standard + Legacy Fallback)
Capital Strata Systems

Primary journal:
  audit_logs/journal.jsonl

Rules:
- Preferred key in journal lines: customer_acct (canonical 10 digits)
- Legacy fallback: account_no (current schema)
- side = DR/CR, amount is numeric string
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from engine.accounting.account_ids import (
    validate_customer_acct,
    format_account_id,
    try_normalize_10digits,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
PRIMARY_JOURNAL = REPO_ROOT / "audit_logs" / "journal.jsonl"
OVERRIDE_JOURNAL = REPO_ROOT / "audit_logs" / "overrides.jsonl"


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                v = json.loads(line)
                if isinstance(v, dict):
                    out.append(v)
            except Exception:
                continue
    return out


def _date_only(entry: Dict[str, Any]) -> Optional[str]:
    # Your schema uses execution_date
    d = entry.get("execution_date") or entry.get("created_at")
    if isinstance(d, str) and len(d) >= 10:
        return d[:10]
    return None


def _in_range(d: Optional[str], from_date: Optional[str], to_date: Optional[str]) -> bool:
    # YYYY-MM-DD string compare is safe for ordering
    if d is None:
        return True
    if from_date and d < from_date:
        return False
    if to_date and d > to_date:
        return False
    return True


def _amount(entry: Dict[str, Any]) -> float:
    try:
        return float(str(entry.get("amount", "0")).replace(",", "").strip())
    except Exception:
        return 0.0


def generate_customer_subledger(
    customer_acct: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> Dict[str, Any]:

    if not PRIMARY_JOURNAL.exists():
        raise FileNotFoundError("audit_logs/journal.jsonl not found (primary journal)")

    cust_canonical = validate_customer_acct(customer_acct)
    cust_display = format_account_id(cust_canonical)

    journal_rows = _read_jsonl(PRIMARY_JOURNAL)
    override_rows = _read_jsonl(OVERRIDE_JOURNAL)

    rows: List[Dict[str, Any]] = []
    running = 0.0

    for e in journal_rows:
        d = _date_only(e)
        if not _in_range(d, from_date, to_date):
            continue

        # Preferred: journal carries customer_acct
        j_cust = try_normalize_10digits(e.get("customer_acct")) or try_normalize_10digits(e.get("customer_account"))
        if j_cust:
            if j_cust != cust_canonical:
                continue
            account_key = j_cust
            account_key_type = "customer_acct"
        else:
            # Legacy fallback: treat requested customer_acct as account_no
            # (This makes Phase-1C usable immediately with current journal schema.)
            if str(e.get("account_no")) != str(cust_canonical):
                continue
            account_key = str(e.get("account_no"))
            account_key_type = "account_no"

        side = (e.get("side") or "").upper().strip()
        amt = _amount(e)

        debit = amt if side == "DR" else 0.0
        credit = amt if side == "CR" else 0.0
        running += (debit - credit)

        rows.append(
            {
                "date": d,
                "journal_id": e.get("journal_id"),
                "ticket_id": e.get("ticket_id"),
                "entry_hash": e.get("entry_hash"),
                "account_key": account_key,
                "account_key_type": account_key_type,
                "currency": e.get("currency"),
                "debit": round(debit, 2),
                "credit": round(credit, 2),
                "running_balance": round(running, 2),
            }
        )

    rows.sort(key=lambda r: ((r.get("date") or ""), (r.get("journal_id") or ""), (r.get("ticket_id") or "")))

    # Recompute running after sort (canonical print order)
    run2 = 0.0
    for r in rows:
        run2 += float(r.get("debit", 0.0)) - float(r.get("credit", 0.0))
        r["running_balance"] = round(run2, 2)

    return {
        "customer_acct": cust_canonical,
        "customer_acct_display": cust_display,
        "from_date": from_date,
        "to_date": to_date,
        "source": {
            "primary_journal": "audit_logs/journal.jsonl",
            "override_rows_seen": len(override_rows),
            "note": "Uses customer_acct if present; falls back to account_no until postings carry customer_acct.",
        },
        "rows": rows,
        "closing_balance": round(run2, 2),
        "stats": {
            "journal_lines_read": len(journal_rows),
            "rows_emitted": len(rows),
        },
    }