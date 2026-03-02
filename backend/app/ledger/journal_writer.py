"""
Capital Strata Systems (CSS)
Phase 30 – Immutable Journal Writer (Hash-Chained)

Features:
- SHA256 integrity hash
- Hash chained to previous entry
- Immutable append-only journal
- Tamper detection ready
"""

from __future__ import annotations

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from uuid import uuid4
from decimal import Decimal

JOURNAL_FILE = Path("audit_logs/journal.jsonl")


# ============================================================
# Utilities
# ============================================================

def _hash_string(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _get_last_hash() -> str:
    if not JOURNAL_FILE.exists():
        return "GENESIS"

    last_hash = "GENESIS"
    with JOURNAL_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                j = json.loads(line)
                last_hash = j.get("entry_hash", last_hash)
            except Exception:
                continue

    return last_hash


# ============================================================
# Core Writer
# ============================================================

def post_transaction(
    *,
    ticket_id: str,
    maker_user_id: str,
    execution_date: str,
    value_date: str,
    description: str,
    currency: str,
    override: Dict[str, Any] | None,
    entries: List[Dict[str, Any]],
) -> Dict[str, Any]:

    if not entries:
        raise ValueError("No entries provided")

    total_dr = Decimal("0")
    total_cr = Decimal("0")

    for e in entries:
        amt = Decimal(str(e["amount"]))
        if e["side"] == "DR":
            total_dr += amt
        elif e["side"] == "CR":
            total_cr += amt

    if total_dr != total_cr:
        raise ValueError("Unbalanced transaction")

    JOURNAL_FILE.parent.mkdir(parents=True, exist_ok=True)

    transaction_id = f"TXN-{uuid4().hex.upper()}"
    previous_hash = _get_last_hash()
    entries_written = 0

    with JOURNAL_FILE.open("a", encoding="utf-8") as f:

        for e in entries:

            entry_id = f"ENT-{uuid4().hex.upper()}"

            record = {
                "journal_id": entry_id,
                "transaction_id": transaction_id,
                "ticket_id": ticket_id,
                "account_no": e["account_no"],
                "side": e["side"],
                "amount": str(e["amount"]),
                "execution_date": execution_date,
                "transaction_date": execution_date,
                "value_date": value_date,
                "description": description,
                "currency": currency,
                "maker_user_id": maker_user_id,
                "override": override,
                "created_at": datetime.utcnow().isoformat() + "Z",
                "previous_hash": previous_hash,
            }

            # Create deterministic string
            hash_input = json.dumps(record, sort_keys=True)
            entry_hash = _hash_string(hash_input)

            record["entry_hash"] = entry_hash

            f.write(json.dumps(record) + "\n")

            previous_hash = entry_hash
            entries_written += 1

    return {
        "status": "POSTED",
        "transaction_id": transaction_id,
        "entries_written": entries_written,
    }