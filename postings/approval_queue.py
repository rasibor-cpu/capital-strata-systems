"""
Approval Queue (Self-contained)
-------------------------------
Phase 11 — Deterministic approval worklist builder.

This module MUST NOT import other postings modules (to avoid missing-module issues).
It also MUST NOT import itself.

Ticket contract (dict):
{
  "ticket_id": str,
  "status": "SUBMITTED" | ...,
  "amount": Decimal,
  "currency": str,
  "posting_type": str,
  "maker_user": str,
  "submitted_at": Optional[str]   # ISO string
}
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, List, Optional, Dict, Any


# -----------------------------
# Thresholds (LOCKED)
# -----------------------------

AUTO_MAX = Decimal("2000000")
USER_MAX = Decimal("15000000")
SUPERVISOR_MAX = Decimal("50000000")
ADMIN_MAX = Decimal("200000000")


def required_level_for_amount(amount: Decimal) -> str:
    if amount <= Decimal("0"):
        raise ValueError("amount must be > 0")
    if amount <= AUTO_MAX:
        return "AUTO"
    if amount <= USER_MAX:
        return "USER"
    if amount <= SUPERVISOR_MAX:
        return "SUPERVISOR"
    if amount <= ADMIN_MAX:
        return "ADMIN"
    return "SUPER"


@dataclass(frozen=True)
class ApprovalQueueItem:
    ticket_id: str
    amount: Decimal
    currency: str
    posting_type: str
    maker_user: str
    required_level: str
    submitted_at: Optional[str]


def build_approval_queue(tickets: Iterable[Dict[str, Any]]) -> List[ApprovalQueueItem]:
    """
    Ordering rules (deterministic):
    1) Higher required approval level first (SUPER > ADMIN > SUPERVISOR > USER > AUTO)
    2) Higher amount first
    3) Earlier submitted_at first (None last)
    4) ticket_id final tie-breaker
    """

    level_weight = {
        "SUPER": 50,
        "ADMIN": 40,
        "SUPERVISOR": 30,
        "USER": 10,
        "AUTO": 0,
    }

    queue: List[ApprovalQueueItem] = []

    for t in tickets:
        if str(t.get("status", "")).upper() != "SUBMITTED":
            continue

        amount = t.get("amount")
        if not isinstance(amount, Decimal):
            raise ValueError("ticket.amount must be Decimal")

        required = required_level_for_amount(amount)

        queue.append(
            ApprovalQueueItem(
                ticket_id=str(t.get("ticket_id", "")),
                amount=amount,
                currency=str(t.get("currency", "")),
                posting_type=str(t.get("posting_type", "")),
                maker_user=str(t.get("maker_user", "")),
                required_level=required,
                submitted_at=t.get("submitted_at"),
            )
        )

    def sort_key(q: ApprovalQueueItem):
        submitted = q.submitted_at or "9999-12-31T23:59:59Z"
        return (
            -level_weight.get(q.required_level, 0),
            -q.amount,
            submitted,
            q.ticket_id,
        )

    queue.sort(key=sort_key)
    return queue
