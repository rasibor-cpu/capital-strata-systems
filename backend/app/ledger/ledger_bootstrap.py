"""
ledger_bootstrap.py
Capital Strata Systems (CSS)

Ledger Startup Rebuild (Phase 1 Recovery)
-----------------------------------------

Goal:
- Rebuild in-memory ledger state from the persisted append-only journal log.

Principle:
- Journal is the system-of-record.
- LedgerStore is derived state rebuilt at startup.

Fail-closed:
- If any journal line cannot be replayed, raise and stop startup.
  (Institutional rule: do not run with corrupted / partial state.)
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List

from app.ledger_registry import get_ledger_engine
from app.ledger.ledger_engine import PostingLine
from app.ledger.journal_persistence import load_all_payloads


def _parse_dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


def _parse_dec(s: str) -> Decimal:
    return Decimal(str(s))


def rebuild_from_journal_log(*, strict: bool = True) -> int:
    """
    Rebuild ledger state by replaying all persisted journal payloads.

    Returns:
      number of journals replayed

    strict=True:
      - any error raises and aborts (recommended)
    strict=False:
      - skips bad lines (NOT recommended for production)
    """
    engine = get_ledger_engine()
    payloads = load_all_payloads()

    replayed = 0

    for obj in payloads:
        try:
            tx_id = obj["transaction_id"]
            tx_date = _parse_dt(obj["transaction_date"])
            val_date = _parse_dt(obj["value_date"])
            ccy = obj["currency"]
            desc = obj.get("description", "")

            lines_obj: List[Dict[str, Any]] = obj["lines"]
            lines: List[PostingLine] = []

            for ln in lines_obj:
                lines.append(
                    PostingLine(
                        account_id=ln["account_id"],
                        debit=_parse_dec(ln.get("debit", "0.00")),
                        credit=_parse_dec(ln.get("credit", "0.00")),
                    )
                )

            engine.post_journal(
                transaction_id=tx_id,
                transaction_date=tx_date,
                value_date=val_date,
                currency=ccy,
                description=desc,
                lines=lines,
            )

            replayed += 1

        except Exception:
            if strict:
                raise
            # else skip corrupted payload
            continue

    return replayed