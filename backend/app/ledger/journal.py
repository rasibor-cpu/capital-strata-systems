"""
journal.py
Capital Strata Systems (CSS)

Journal Posting Integration Layer
---------------------------------

Includes:
- Auto transaction_id generation (system reference)
- Append-only journal persistence (JSONL)
- Real-time ledger posting (single engine/store via registry)

Idempotency:
- Engine blocks only when SAME transaction_id is re-used on SAME transaction date.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Optional, Any
import uuid

from app.ledger_registry import get_ledger_engine
from app.ledger.ledger_engine import PostingLine
from app.ledger.journal_persistence import append_payload


@dataclass(frozen=True)
class JournalLine:
    account_id: str
    debit: Decimal = Decimal("0.00")
    credit: Decimal = Decimal("0.00")
    dims: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class JournalEntry:
    transaction_id: str
    transaction_date: datetime
    value_date: datetime
    currency: str
    description: str
    lines: List[JournalLine]
    meta: Optional[Dict[str, Any]] = None


def _gen_tx_id(now: datetime) -> str:
    # Unique, traceable, sortable enough for Phase 1
    # Example: CSS-20260227-2f8c0f7e3b2a4c1a
    return f"CSS-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:16]}"


def _serialize_entry(entry: JournalEntry) -> Dict[str, Any]:
    return {
        "transaction_id": entry.transaction_id,
        "transaction_date": entry.transaction_date.isoformat(),
        "value_date": entry.value_date.isoformat(),
        "currency": entry.currency,
        "description": entry.description,
        "lines": [
            {
                "account_id": ln.account_id,
                "debit": str(ln.debit),
                "credit": str(ln.credit),
                "dims": ln.dims or {},
            }
            for ln in entry.lines
        ],
        "meta": entry.meta or {},
    }


def _require_nonempty(s: str, field: str) -> str:
    v = (s or "").strip()
    if not v:
        raise ValueError(f"{field} is required.")
    return v


def _normalize_ccy(ccy: str) -> str:
    c = _require_nonempty(ccy, "currency").upper()
    if len(c) != 3 or not c.isalpha():
        raise ValueError("currency must be a 3-letter code.")
    return c


def _validate_lines(lines: List[JournalLine]) -> None:
    if not lines or len(lines) < 2:
        raise ValueError("Journal must contain at least two lines.")

    total_debit = Decimal("0.00")
    total_credit = Decimal("0.00")

    for ln in lines:
        _require_nonempty(ln.account_id, "account_id")

        if ln.debit > 0 and ln.credit > 0:
            raise ValueError("Line cannot contain both debit and credit.")
        if ln.debit < 0 or ln.credit < 0:
            raise ValueError("Amounts cannot be negative.")
        if ln.debit == 0 and ln.credit == 0:
            raise ValueError("Line must contain debit or credit.")

        total_debit += ln.debit
        total_credit += ln.credit

    if total_debit != total_credit:
        raise ValueError(f"Unbalanced journal: debit {total_debit} != credit {total_credit}")


def post_journal(entry: JournalEntry) -> Dict[str, Decimal]:
    if not isinstance(entry.transaction_date, datetime):
        raise ValueError("transaction_date must be datetime.")
    if not isinstance(entry.value_date, datetime):
        raise ValueError("value_date must be datetime.")

    # Auto-assign unique transaction reference if blank/AUTO
    tx_id_raw = (entry.transaction_id or "").strip()
    tx_id = tx_id_raw if tx_id_raw and tx_id_raw.upper() != "AUTO" else _gen_tx_id(entry.transaction_date)

    desc = _require_nonempty(entry.description, "description")
    ccy = _normalize_ccy(entry.currency)

    _validate_lines(entry.lines)

    # Persist system-of-record
    persisted_entry = JournalEntry(
        transaction_id=tx_id,
        transaction_date=entry.transaction_date,
        value_date=entry.value_date,
        currency=ccy,
        description=desc,
        lines=entry.lines,
        meta=entry.meta,
    )
    append_payload(_serialize_entry(persisted_entry))

    # Post derived state
    engine = get_ledger_engine()
    posting_lines: List[PostingLine] = [
        PostingLine(account_id=ln.account_id, debit=ln.debit, credit=ln.credit)
        for ln in persisted_entry.lines
    ]

    return engine.post_journal(
        transaction_id=tx_id,
        transaction_date=persisted_entry.transaction_date,
        value_date=persisted_entry.value_date,
        currency=ccy,
        description=desc,
        lines=posting_lines,
    )