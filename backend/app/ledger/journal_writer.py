"""
Capital Strata Systems
Phase 18A – Atomic Journal Writer (Institutional Grade)

Guarantees:
- Per-transaction DR = CR validation
- Atomic append of all legs
- Global journal balance verification
- Fail-closed on corruption
- UTF-8 (no BOM) enforced
"""

from __future__ import annotations

import json
from pathlib import Path
from decimal import Decimal
from datetime import datetime
from typing import List, Dict


JOURNAL_FILE = Path("audit_logs/journal.jsonl")


def _to_decimal(val) -> Decimal:
    return Decimal(str(val))


def _ensure_journal_exists():
    JOURNAL_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not JOURNAL_FILE.exists():
        JOURNAL_FILE.write_text("", encoding="utf-8")


def _validate_transaction(entries: List[Dict]):
    total_dr = Decimal("0")
    total_cr = Decimal("0")

    for e in entries:
        amt = _to_decimal(e["amount"])
        if e["side"] == "DR":
            total_dr += amt
        elif e["side"] == "CR":
            total_cr += amt
        else:
            raise ValueError(f"Invalid side: {e['side']}")

    if total_dr != total_cr:
        raise ValueError(
            f"Unbalanced transaction: DR={total_dr}, CR={total_cr}"
        )


def _validate_global_balance():
    dr = Decimal("0")
    cr = Decimal("0")

    with JOURNAL_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            j = json.loads(line)
            amt = _to_decimal(j["amount"])
            if j["side"] == "DR":
                dr += amt
            elif j["side"] == "CR":
                cr += amt

    if dr != cr:
        raise RuntimeError(
            f"Journal globally unbalanced. DR={dr}, CR={cr}"
        )


def post_transaction(ticket_id: str, entries: List[Dict]):
    """
    Post balanced transaction atomically.
    """

    _ensure_journal_exists()

    # Fail if journal already corrupted
    _validate_global_balance()

    # Validate transaction
    _validate_transaction(entries)

    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    records = []

    for e in entries:
        record = {
            "journal_id": f"J-{datetime.now().timestamp()}",
            "ticket_id": ticket_id,
            "execution_date": datetime.now().strftime("%Y-%m-%d"),
            "account_no": e["account_no"],
            "side": e["side"],
            "amount": str(e["amount"]),
            "created_at": timestamp,
        }
        records.append(json.dumps(record))

    # Atomic append (single write operation)
    with JOURNAL_FILE.open("a", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(records) + "\n")

    # Verify integrity after write
    _validate_global_balance()

    return True