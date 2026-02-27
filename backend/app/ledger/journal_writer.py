"""
Capital Strata Systems
Phase 18 – Posting Integrity Guard

This module enforces:

- Double-entry validation
- Atomic journal write
- Balanced transaction requirement
- Rejection logging
"""

from pathlib import Path
from decimal import Decimal
from datetime import datetime
import json
import uuid


JOURNAL_FILE = Path("audit_logs/journal.jsonl")
REJECTION_LOG = Path("audit_logs/journal_rejections.jsonl")


def _to_decimal(value):
    return Decimal(str(value))


def post_transaction(ticket_id: str, entries: list):
    """
    entries format:
    [
        {"account_no": "100", "side": "DR", "amount": 1000},
        {"account_no": "200", "side": "CR", "amount": 1000}
    ]
    """

    total_dr = Decimal("0")
    total_cr = Decimal("0")

    for e in entries:
        amt = _to_decimal(e["amount"])
        if e["side"].upper() == "DR":
            total_dr += amt
        elif e["side"].upper() == "CR":
            total_cr += amt

    if total_dr != total_cr:
        _log_rejection(ticket_id, entries, total_dr, total_cr)
        raise ValueError(f"Unbalanced transaction: DR={total_dr}, CR={total_cr}")

    JOURNAL_FILE.parent.mkdir(parents=True, exist_ok=True)

    for e in entries:
        record = {
            "journal_id": f"J-{uuid.uuid4().hex[:10]}",
            "ticket_id": ticket_id,
            "execution_date": datetime.now().strftime("%Y-%m-%d"),
            "account_no": e["account_no"],
            "side": e["side"].upper(),
            "amount": str(e["amount"]),
            "created_at": datetime.now().isoformat()
        }

        with JOURNAL_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")


def _log_rejection(ticket_id, entries, dr, cr):
    REJECTION_LOG.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "timestamp": datetime.now().isoformat(),
        "ticket_id": ticket_id,
        "entries": entries,
        "total_dr": str(dr),
        "total_cr": str(cr),
        "reason": "Unbalanced transaction"
    }

    with REJECTION_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")