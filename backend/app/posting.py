"""
Posting Entry Screen
Phase 13.4.2

- Validates posting payload
- Creates DRAFT ticket in posting_store
- NO ledger writes
"""

from datetime import datetime

from .posting_contracts import (
    PostingTicket,
    TicketStatus,
)
from .posting_validation import validate_posting_payload
from .posting_store import create_ticket


def handle(payload: dict, user_id: str) -> dict:
    # 1. Validate input
    result = validate_posting_payload(payload)
    if not result.ok:
        return {
            "screen": "posting_entry",
            "status": "error",
            "message": "Validation failed",
            "errors": result.errors,
        }

    # 2. Create ticket
    ticket = PostingTicket(
        ticket_id=payload["ticket_id"],
        execution_date=payload["execution_date"],
        value_date=payload["value_date"],
        currency=payload["lines"][0]["currency"],
        total_amount=sum(l["amount"] for l in payload["lines"]),
        status=TicketStatus.DRAFT,
        created_by=user_id,
        created_at=datetime.utcnow(),
        lines=payload["lines"],
    )

    create_ticket(ticket)

    # 3. Return orchestration response
    return {
        "screen": "posting_entry",
        "status": "ok",
        "message": "Draft ticket created",
        "data": {
            "ticket_id": ticket.ticket_id,
            "status": ticket.status,
            "next_action": "submit",
        },
    }
