"""
Posting lifecycle screen handlers (Phase 13.5)

Implements:
- posting_review: read-only view of a ticket
- posting_submit: maker submits DRAFT -> SUBMITTED
(no ledger write; store-only)

These handlers operate on the in-memory posting_store.
"""

from typing import Dict, Any

from ..posting_store import get_ticket, submit_ticket
from ..posting_contracts import ticket_totals


def posting_review_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    ticket_id = str(payload.get("ticket_id", "")).strip()
    if not ticket_id:
        return {"ok": False, "error": "ticket_id is required"}

    ticket = get_ticket(ticket_id)
    if not ticket:
        return {"ok": False, "error": f"Ticket not found: {ticket_id}"}

    totals = ticket_totals(ticket)

    return {
        "ok": True,
        "ticket": {
            "ticket_id": ticket.ticket_id,
            "status": ticket.status.value,
            "created_by": ticket.created_by,
            "created_at": ticket.created_at.isoformat(),
            "submitted_at": (ticket.submitted_at.isoformat() if ticket.submitted_at else None),
            "execution_date": ticket.execution_date,
            "value_date": ticket.value_date,
            "is_fx": ticket.is_fx,
            "rate": ticket.rate,
            "counter_currency": ticket.counter_currency,
            "line_count": len(ticket.lines),
            "last_comment": ticket.last_comment,
        },
        "lines": [ln.__dict__ for ln in ticket.lines],
        "totals": totals,
        "approvals": ticket.approvals,
        "note": "Read-only review. No changes applied.",
    }


def posting_submit_handler(payload: Dict[str, Any], user_id: str | None) -> Dict[str, Any]:
    ticket_id = str(payload.get("ticket_id", "")).strip()
    if not ticket_id:
        return {"ok": False, "error": "ticket_id is required"}

    maker_id = user_id or "anonymous"

    try:
        ticket = submit_ticket(ticket_id, maker_id)
        return {
            "ok": True,
            "message": "Ticket submitted",
            "ticket": {
                "ticket_id": ticket.ticket_id,
                "status": ticket.status.value,
                "submitted_at": ticket.submitted_at.isoformat() if ticket.submitted_at else None,
            },
            "next_actions": ["checker_review", "checker_decision"],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}
