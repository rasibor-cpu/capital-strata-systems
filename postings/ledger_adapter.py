"""
postings/ledger_adapter.py
-------------------------
Bridge: PostingTicket (maker-checker) -> PostingLedger (governance-grade).

Design goals:
- Do NOT modify PostingTicket models
- Treat PostingLedger as the authoritative append-only ledger sink
- Create exactly two PostingEntry rows per approved ticket: DR + CR
- Enforce approval level requirements before posting

This adapter is intentionally minimal and deterministic.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from postings.models import PostingTicket, PostingStatus
from posting_ledger import PostingLedger, PostingEntry, APPROVAL_ORDER


def _require(condition: bool, msg: str) -> None:
    if not condition:
        raise ValueError(msg)


def _normalize_ccy(ccy: str) -> str:
    c = (ccy or "").strip().upper()
    _require(len(c) == 3, "currency must be a 3-letter code (e.g., USD)")
    return c


def _to_float_amount(amount: Decimal) -> float:
    # PostingLedger uses float; keep conversion deterministic
    _require(amount > Decimal("0"), "amount must be > 0")
    return float(amount.quantize(Decimal("0.01")))


def _approval_level_ok(required_level: int, approver_level: Optional[str]) -> bool:
    # required_level: 0 (AUTO) ... 5 (SUPER)
    # approver_level: "USER"/"SUPERVISOR"/"MANAGER"/"ADMIN"/"SUPER"/None
    req = int(required_level)
    _require(0 <= req <= 5, "approval_level_required must be between 0 and 5")
    if req == 0:
        return True
    if not approver_level:
        return False
    got = APPROVAL_ORDER.get(approver_level.upper())
    return got is not None and got >= req


def post_approved_ticket_to_ledger(
    *,
    ledger: PostingLedger,
    ticket: PostingTicket,
    customer_id: str,
    customer_name: str,
    account_ref: str,
    customer_type: str = "CUSTOMER",
    ledger_type: str = "CUSTOMER",
    domain: str = "TREASURY",
    transaction_type: str = "POSTING",
    fx_pair: Optional[str] = None,
    price: Optional[float] = None,
    value_date: Optional[str] = None,
    booking_date: Optional[str] = None,
    approver_level: Optional[str] = None,
) -> None:
    """
    Convert an APPROVED PostingTicket into two ledger entries (DR + CR).

    Required:
    - ledger: PostingLedger instance
    - ticket: PostingTicket (must be APPROVED)
    - customer_id/customer_name/account_ref: customer context for governance reporting

    Approval:
    - ticket.approval_level_required is enforced against approver_level ("USER", "SUPERVISOR", ...)

    Notes:
    - booking_date defaults to today's UTC date (YYYY-MM-DD)
    - value_date may be None for simple postings
    """

    _require(ticket.status == PostingStatus.APPROVED, "ticket must be APPROVED before posting")
    _require(ticket.debit_account.strip() != "", "ticket.debit_account is required")
    _require(ticket.credit_account.strip() != "", "ticket.credit_account is required")
    _require(customer_id.strip() != "", "customer_id is required")
    _require(customer_name.strip() != "", "customer_name is required")
    _require(account_ref.strip() != "", "account_ref is required")

    _require(
        _approval_level_ok(ticket.approval_level_required, approver_level),
        "approval level insufficient for posting",
    )

    ccy = _normalize_ccy(ticket.currency)
    amt = _to_float_amount(ticket.amount)

    book_date = booking_date or datetime.utcnow().date().isoformat()
    desc = ticket.description.strip() or f"Posting ticket {ticket.ticket_id}"

    # DR entry
    dr = PostingEntry(
        entry_id=str(ticket.ticket_id) + "::DR",
        customer_id=customer_id.strip(),
        customer_name=customer_name.strip(),
        account_ref=account_ref.strip(),
        customer_type=customer_type.strip().upper(),

        ledger_type=ledger_type.strip().upper(),
        ledger_id=ticket.debit_account.strip(),
        domain=domain.strip().upper(),

        transaction_type=transaction_type.strip().upper(),
        side="DR",
        currency=ccy,
        notional=amt,
        fx_pair=fx_pair,
        price=price,
        value_date=value_date,
        booking_date=book_date,
        description=desc,

        approved_by=ticket.approver_user,
        approval_level=(approver_level or "").upper() if approver_level else None,
    )

    # CR entry
    cr = PostingEntry(
        entry_id=str(ticket.ticket_id) + "::CR",
        customer_id=customer_id.strip(),
        customer_name=customer_name.strip(),
        account_ref=account_ref.strip(),
        customer_type=customer_type.strip().upper(),

        ledger_type=ledger_type.strip().upper(),
        ledger_id=ticket.credit_account.strip(),
        domain=domain.strip().upper(),

        transaction_type=transaction_type.strip().upper(),
        side="CR",
        currency=ccy,
        notional=amt,
        fx_pair=fx_pair,
        price=price,
        value_date=value_date,
        booking_date=book_date,
        description=desc,

        approved_by=ticket.approver_user,
        approval_level=(approver_level or "").upper() if approver_level else None,
    )

    # Append-only ledger write
    ledger.add_entry(dr)
    ledger.add_entry(cr)

    # Mark ticket posted (domain model)
    ticket.mark_posted()
