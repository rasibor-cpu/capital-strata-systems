"""
postings/checker_approval.py
----------------------------
Checker (approver) screen logic (UI-agnostic).

Responsibilities:
- Approve or reject a submitted PostingTicket
- Enforce that required approval level is met
- Optionally post to PostingLedger after approval (hooked via adapter)

This module does NOT implement UI; it defines a clean contract for UI calls.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any

from postings.api import PostingStore
from postings.models import PostingTicket, PostingStatus
from posting_ledger import PostingLedger, APPROVAL_ORDER
from postings.ledger_adapter import post_approved_ticket_to_ledger


@dataclass
class CheckerActionInput:
    ticket_id: str
    action: str  # "APPROVE" | "REJECT"
    approver_user: str
    approver_level: str  # USER / SUPERVISOR / MANAGER / ADMIN / SUPER
    reject_reason: str = ""

    # Customer context (required to post into ledger)
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    account_ref: Optional[str] = None


def _norm(s: str) -> str:
    return (s or "").strip()


def _norm_upper(s: str) -> str:
    return _norm(s).upper()


def _require(condition: bool, msg: str) -> None:
    if not condition:
        raise ValueError(msg)


def _approval_level_ok(required_level: int, approver_level: str) -> bool:
    req = int(required_level)
    _require(0 <= req <= 5, "approval_level_required must be between 0 and 5")
    if req == 0:
        return True
    got = APPROVAL_ORDER.get(_norm_upper(approver_level))
    return got is not None and got >= req


def approve_or_reject(
    *,
    store: PostingStore,
    inp: CheckerActionInput,
    ledger: Optional[PostingLedger] = None,
    auto_post: bool = False,
) -> PostingTicket:
    """
    Approve/reject a SUBMITTED ticket. If auto_post=True, requires ledger + customer context.
    """

    ticket_id = _norm(inp.ticket_id)
    action = _norm_upper(inp.action)
    approver_user = _norm(inp.approver_user)
    approver_level = _norm_upper(inp.approver_level)

    _require(ticket_id != "", "ticket_id is required")
    _require(action in ("APPROVE", "REJECT"), "action must be APPROVE or REJECT")
    _require(approver_user != "", "approver_user is required")
    _require(approver_level in APPROVAL_ORDER, "approver_level must be USER/SUPERVISOR/MANAGER/ADMIN/SUPER")

    t = store.get(ticket_id)

    _require(t.status == PostingStatus.SUBMITTED, "ticket must be SUBMITTED for checker action")
    _require(_approval_level_ok(t.approval_level_required, approver_level), "approval level insufficient")

    if action == "REJECT":
        reason = _norm(inp.reject_reason)
        _require(reason != "", "reject_reason is required for REJECT")
        # Domain model currently doesn't store reason; we can attach later in audit logs
        t = store.reject(ticket_id, approver_user=approver_user)
        return t

    # APPROVE
    t = store.approve(ticket_id, approver_user=approver_user)

    if auto_post:
        _require(ledger is not None, "ledger is required when auto_post=True")
        _require(_norm(inp.customer_id) != "", "customer_id required for posting")
        _require(_norm(inp.customer_name) != "", "customer_name required for posting")
        _require(_norm(inp.account_ref) != "", "account_ref required for posting")

        post_approved_ticket_to_ledger(
            ledger=ledger,
            ticket=t,
            customer_id=_norm(inp.customer_id),
            customer_name=_norm(inp.customer_name),
            account_ref=_norm(inp.account_ref),
            customer_type="CUSTOMER",
            ledger_type="CUSTOMER",
            domain="TREASURY",
            transaction_type="POSTING",
            approver_level=approver_level,
        )

    return t


def input_from_dict(d: Dict[str, Any]) -> CheckerActionInput:
    return CheckerActionInput(
        ticket_id=str(d.get("ticket_id", "")),
        action=str(d.get("action", "")),
        approver_user=str(d.get("approver_user", "")),
        approver_level=str(d.get("approver_level", "")),
        reject_reason=str(d.get("reject_reason", "")),
        customer_id=d.get("customer_id"),
        customer_name=d.get("customer_name"),
        account_ref=d.get("account_ref"),
    )
