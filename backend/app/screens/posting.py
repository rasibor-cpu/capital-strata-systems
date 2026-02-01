"""
Posting screen handlers (Phase 13.3)

Implements posting_entry as validation-first (no persistence, no execution).
"""

from typing import Dict, Any

from ..posting_contracts import PostingTicket, PostingLine, ticket_totals
from ..posting_validation import validate_ticket


def posting_entry_handler(payload: Dict[str, Any], user_id: str | None) -> Dict[str, Any]:
    """
    Expected payload (draft form):
      {
        "ticket_id": "T-0001",
        "execution_date": "2026-02-01",
        "value_date": "2026-02-01",
        "lines": [
          {"side":"DR","account_no":"...","currency":"UNITED STATES DOLLAR","amount":1000,"narrative":"..."},
          {"side":"CR","account_no":"...","currency":"UNITED STATES DOLLAR","amount":1000,"narrative":"..."}
        ]
      }

    Returns:
      - normalized totals
      - validation errors list
      - is_valid boolean
    """
    lines_in = payload.get("lines", []) or []

    lines = []
    for ln in lines_in:
        lines.append(
            PostingLine(
                side=str(ln.get("side", "")).upper(),
                account_no=str(ln.get("account_no", "")).strip(),
                currency=str(ln.get("currency", "")).strip(),
                amount=float(ln.get("amount", 0.0)),
                narrative=str(ln.get("narrative", "")).strip(),
            )
        )

    ticket = PostingTicket(
        ticket_id=str(payload.get("ticket_id", "")).strip() or "T-UNSPECIFIED",
        created_by=user_id or "anonymous",
        execution_date=str(payload.get("execution_date", "")).strip(),
        value_date=str(payload.get("value_date", "")).strip(),
        is_fx=bool(payload.get("is_fx", False)),
        rate=payload.get("rate", None),
        counter_currency=payload.get("counter_currency", None),
        lines=lines,
        meta={"source": "posting_entry"},
    )

    errors = validate_ticket(ticket)
    totals = ticket_totals(ticket)

    return {
        "ticket": {
            "ticket_id": ticket.ticket_id,
            "created_by": ticket.created_by,
            "execution_date": ticket.execution_date,
            "value_date": ticket.value_date,
            "is_fx": ticket.is_fx,
            "rate": ticket.rate,
            "counter_currency": ticket.counter_currency,
            "line_count": len(ticket.lines),
        },
        "totals": totals,
        "errors": errors,
        "is_valid": len(errors) == 0,
        "next_actions": ["submit_ticket"] if len(errors) == 0 else ["fix_errors"],
        "note": "Validation-only. No persistence or ledger posting occurs at this stage.",
    }
