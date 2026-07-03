"""
Posting Contracts (Phase 13.3)

Defines the canonical maker-checker posting ticket structure.

Hard constraints:
- This layer does NOT execute ledger writes.
- It models tickets, validations, and approvals only.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional, List
import datetime


def _utc_now_compat() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


class TicketStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    RETURNED = "returned"
    REJECTED = "rejected"
    APPROVED = "approved"


class ApprovalDecision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    RETURN = "return"


@dataclass
class PostingLine:
    """
    A single debit or credit line.

    amount is ALWAYS positive.
    side determines debit/credit.
    currency must be full text (Phase 13 governance).
    """
    side: str  # "DR" or "CR"
    account_no: str
    currency: str  # e.g., "UNITED STATES DOLLAR"
    amount: float
    narrative: str = ""


@dataclass
class PostingTicket:
    """
    Maker ticket (one posting instruction).
    """
    ticket_id: str
    created_by: str
    created_at: datetime.datetime = field(default_factory=_utc_now_compat)

    status: TicketStatus = TicketStatus.DRAFT
    submitted_at: Optional[datetime.datetime] = None

    # Core dates (governance)
    execution_date: str = ""  # YYYY-MM-DD
    value_date: str = ""      # YYYY-MM-DD

    # FX-specific (optional)
    is_fx: bool = False
    rate: Optional[float] = None
    counter_currency: Optional[str] = None

    # Lines
    lines: List[PostingLine] = field(default_factory=list)

    # Approvals & audit
    approvals: List[Dict[str, Any]] = field(default_factory=list)
    last_comment: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)


def ticket_totals(ticket: PostingTicket) -> Dict[str, float]:
    dr = 0.0
    cr = 0.0
    for ln in ticket.lines:
        if ln.side.upper() == "DR":
            dr += float(ln.amount)
        elif ln.side.upper() == "CR":
            cr += float(ln.amount)
    return {"dr_total": dr, "cr_total": cr, "balanced": abs(dr - cr) < 0.000001}
