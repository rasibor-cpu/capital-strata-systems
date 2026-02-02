"""
postings/api.py
---------------
API-style functions for posting workflow.

Phase 1:
- In-memory store (dict) for tickets
- Create/submit/approve/reject
- Pure domain logic (no web framework required)

Next phases will add persistence + integration with ledger posting endpoints.
"""

from dataclasses import asdict
from decimal import Decimal
from typing import Dict, Optional, Any
from datetime import datetime

from postings.models import PostingTicket, PostingStatus, PostingType


class PostingStore:
    """
    Minimal in-memory ticket store for development + CLI testing.

    NOTE: This will be replaced by persistence later (sqlite/json/db),
    but we keep the interface stable so UI + services don't change.
    """

    def __init__(self) -> None:
        self._tickets: Dict[str, PostingTicket] = {}

    def create_ticket(
        self,
        *,
        posting_type: PostingType,
        amount: Decimal,
        currency: str,
        debit_account: str,
        credit_account: str,
        maker_user: str,
        description: str = "",
        approval_level_required: int = 0,
    ) -> PostingTicket:
        if amount <= Decimal("0"):
            raise ValueError("amount must be > 0")
        if not currency or len(currency.strip()) != 3:
            raise ValueError("currency must be a 3-letter code (e.g., USD)")
        if not debit_account.strip() or not credit_account.strip():
            raise ValueError("debit_account and credit_account are required")
        if not maker_user.strip():
            raise ValueError("maker_user is required")

        ticket = PostingTicket(
            posting_type=posting_type,
            amount=amount,
            currency=currency.strip().upper(),
            debit_account=debit_account.strip(),
            credit_account=credit_account.strip(),
            maker_user=maker_user.strip(),
            description=description.strip(),
            approval_level_required=int(approval_level_required),
        )
        self._tickets[ticket.ticket_id] = ticket
        return ticket

    def get(self, ticket_id: str) -> PostingTicket:
        ticket = self._tickets.get(ticket_id)
        if not ticket:
            raise KeyError(f"ticket_id not found: {ticket_id}")
        return ticket

    def submit(self, ticket_id: str) -> PostingTicket:
        ticket = self.get(ticket_id)
        ticket.submit()
        return ticket

    def approve(self, ticket_id: str, *, approver_user: str) -> PostingTicket:
        if not approver_user.strip():
            raise ValueError("approver_user is required")
        ticket = self.get(ticket_id)
        ticket.approve(approver_user.strip())
        return ticket

    def reject(self, ticket_id: str, *, approver_user: str) -> PostingTicket:
        if not approver_user.strip():
            raise ValueError("approver_user is required")
        ticket = self.get(ticket_id)
        ticket.reject(approver_user.strip())
        return ticket

    def list_tickets(self, status: Optional[PostingStatus] = None) -> Dict[str, PostingTicket]:
        if status is None:
            return dict(self._tickets)
        return {tid: t for tid, t in self._tickets.items() if t.status == status}

    def to_dict(self, ticket_id: str) -> Dict[str, Any]:
        t = self.get(ticket_id)
        d = asdict(t)
        # datetime objects are not JSON-serializable by default
        for k in ("created_at", "submitted_at", "approved_at", "posted_at"):
            if isinstance(d.get(k), datetime):
                d[k] = d[k].isoformat() + "Z"
            elif d.get(k) is None:
                d[k] = None
        # Enum values
        d["status"] = t.status.value
        d["posting_type"] = t.posting_type.value
        # Decimal -> string
        d["amount"] = str(t.amount)
        return d
