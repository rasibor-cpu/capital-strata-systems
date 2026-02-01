"""
Posting screen handlers (Phase 13)

Implements posting_entry as:
- Build PostingTicket from payload
- Validate (balanced DR/CR, currency full-text, dates, etc.)
- If valid: create DRAFT ticket in in-memory store
- NO persistence beyond in-memory store
- NO ledger writes
"""

from typing import Dict, Any

from ..posting_contracts import PostingTicket, PostingLine, ticket_totals, TicketStatus
from ..posting_validation import validate_ticket
from ..posting_store import create_ticket


def posting_entry_handler(payload: Dict[str, Any], user_id: str | None) -> Dict[str, Any]:
    """
    Expected payload:
      {
        "ticket_id": "T-0001",
        "execution_date": "2026-02-01",
        "value_date": "2026-02-01",
        "lines": [
          {"side":"DR","account_no":"...","currency":"UNITED STATES DOLLAR","amount":1000,"narrative":"..."},
          {"side":"CR","account_no":"...","currency":"UNITED STATES DOLLAR","amount":1000,"narrative":"..."}
        ]
      }

    Behavior:
    - Validate ticket
    - If valid: store as DRAFT in posting_store
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

    if errors:
        return {
            "ticket": {
                "ticket_id": ticket.ticket_id,
                "created_by": ticket.created_by,
                "execution_date": ticket.execution_date,
                "value_date": ticket.value_date,
                "status": ticket.status.value,
                "line_count": len(ticket.lines),
            },
            "totals": totals,
            "errors": errors,
            "is_valid": False,
            "stored": False,
            "next_actions": ["fix_errors"],
            "note": "Validation failed. Ticket was NOT stored.",
        }

    # Store draft ticket (in-memory)
    try:
        ticket.status = TicketStatus.DRAFT
        create_ticket(ticket)
        stored_ok = True
        store_error = ""
    except Exception as e:
        stored_ok = False
        store_error = str(e)

    return {
        "ticket": {
            "ticket_id": ticket.ticket_id,
            "created_by": ticket.created_by,
            "execution_date": ticket.execution_date,
            "value_date": ticket.value_date,
            "status": ticket.status.value,
            "line_count": len(ticket.lines),
        },
        "totals": totals,
        "errors": ([] if stored_ok else [f"Store error: {store_error}"]),
        "is_valid": stored_ok,
        "stored": stored_ok,
        "next_actions": (["submit_ticket"] if stored_ok else ["retry_store"]),
        "note": "Validation passed. Ticket stored as DRAFT in memory. No ledger posting.",
    }
