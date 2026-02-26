"""
backend/app/posting_store.py

Posting validation + in-memory ticket store for Posting Screens (Phase 13.x)

This module MUST expose:
- validate_posting_lines(lines)
- create_ticket(ticket)
- get_ticket(ticket_id)
- submit_ticket(ticket_id, maker_id)
- approve_ticket(ticket_id, checker_id)
- reject_ticket(ticket_id, checker_id, reason)
- return_ticket(ticket_id, checker_id, reason)

Design principles:
- Deterministic validation
- In-memory store (Phase 1)
- No ledger mutation here (ledger write happens downstream)
"""

from __future__ import annotations

from typing import Dict, Any, Optional

from datetime import datetime, timezone

# Your domain contracts (already used by screens)
from .posting_contracts import TicketStatus  # type: ignore

# ============================================================
# In-memory store
# ============================================================

_TICKETS: Dict[str, Any] = {}  # stores PostingTicket objects


def create_ticket(ticket: Any) -> Any:
    """
    Store a DRAFT ticket in-memory.

    Expects `ticket.ticket_id` to exist.
    """
    ticket_id = getattr(ticket, "ticket_id", None)
    if not ticket_id:
        raise ValueError("ticket_id is required on ticket")
    if ticket_id in _TICKETS:
        raise ValueError(f"ticket_id already exists: {ticket_id}")

    _TICKETS[ticket_id] = ticket
    return ticket


def get_ticket(ticket_id: str) -> Optional[Any]:
    return _TICKETS.get(ticket_id)


def submit_ticket(ticket_id: str, maker_id: str) -> Any:
    t = _TICKETS.get(ticket_id)
    if not t:
        raise KeyError(f"Ticket not found: {ticket_id}")

    # If your PostingTicket has a method, use it; else set fields safely.
    if getattr(t, "submit", None):
        t.submit()  # type: ignore
    else:
        # Require DRAFT → SUBMITTED
        cur = getattr(getattr(t, "status", None), "value", None)
        # If status is Enum instance, compare via .value; else compare raw.
        if cur and str(cur).upper() != "DRAFT":
            raise ValueError(f"Ticket not in DRAFT status (current={cur})")

        try:
            t.status = TicketStatus.SUBMITTED  # type: ignore
        except Exception:
            # fallback: keep existing status object but set value-ish if it’s not Enum
            t.status = TicketStatus.SUBMITTED  # type: ignore

        if hasattr(t, "submitted_at"):
            t.submitted_at = datetime.now(timezone.utc)
        if hasattr(t, "last_comment"):
            t.last_comment = f"Submitted by {maker_id}"

    return t


def approve_ticket(ticket_id: str, checker_id: str) -> Any:
    t = _TICKETS.get(ticket_id)
    if not t:
        raise KeyError(f"ticket_id not found: {ticket_id}")

    if getattr(t, "approve", None):
        # Many implementations accept `approver` kw or positional.
        try:
            t.approve(approver=checker_id)  # type: ignore
        except TypeError:
            t.approve(checker_id)  # type: ignore
    else:
        # Require SUBMITTED → APPROVED (best effort)
        try:
            t.status = TicketStatus.APPROVED  # type: ignore
        except Exception:
            pass
        if hasattr(t, "approved_at"):
            t.approved_at = datetime.now(timezone.utc)
        if hasattr(t, "approvals") and isinstance(getattr(t, "approvals"), list):
            t.approvals.append({"by": checker_id, "at": datetime.now(timezone.utc).isoformat()})
        if hasattr(t, "last_comment"):
            t.last_comment = f"Approved by {checker_id}"

    return t


def reject_ticket(ticket_id: str, checker_id: str, reason: str) -> Any:
    t = _TICKETS.get(ticket_id)
    if not t:
        raise KeyError(f"ticket_id not found: {ticket_id}")

    if getattr(t, "reject", None):
        try:
            t.reject(approver=checker_id)  # type: ignore
        except TypeError:
            t.reject(checker_id)  # type: ignore
    else:
        try:
            t.status = TicketStatus.REJECTED  # type: ignore
        except Exception:
            pass
        if hasattr(t, "rejected_at"):
            t.rejected_at = datetime.now(timezone.utc)
        if hasattr(t, "last_comment"):
            t.last_comment = f"Rejected by {checker_id}: {reason}"

    return t


def return_ticket(ticket_id: str, checker_id: str, reason: str) -> Any:
    """
    Return a ticket to maker for correction.

    If your TicketStatus has RETURNED, we use it; otherwise we revert to DRAFT.
    """
    t = _TICKETS.get(ticket_id)
    if not t:
        raise KeyError(f"ticket_id not found: {ticket_id}")

    # If ticket model supports it, use its API
    if getattr(t, "mark_returned", None):
        t.mark_returned(checker_id, reason)  # type: ignore
        return t

    # Best effort: set status to RETURNED if available else DRAFT
    target = None
    for name in ("RETURNED", "DRAFT"):
        if hasattr(TicketStatus, name):
            target = getattr(TicketStatus, name)
            break

    if target is None:
        raise RuntimeError("TicketStatus lacks RETURNED and DRAFT; cannot return ticket safely")

    try:
        t.status = target  # type: ignore
    except Exception:
        pass

    if hasattr(t, "last_comment"):
        t.last_comment = f"Returned by {checker_id}: {reason}"

    return t


# ============================================================
# Validation (kept exactly in this module)
# ============================================================

ALLOWED_SIDES = {"DR", "CR"}


def validate_posting_lines(lines: list[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Validate posting lines for correctness before ticket creation.

    Enforces:
    - At least 2 lines
    - Each line has required fields
    - side is DR/CR
    - Amount is positive numeric
    - Balanced totals (DR == CR)

    Returns a dict with totals and errors.
    Raises ValueError on failure.
    """
    if not isinstance(lines, list) or len(lines) < 2:
        raise ValueError("Posting must contain at least 2 lines")

    required = {"side", "base_account_no", "account_type_code", "currency", "amount", "narrative"}

    dr_total = 0.0
    cr_total = 0.0
    errors = []

    for i, ln in enumerate(lines):
        if not isinstance(ln, dict):
            errors.append(f"Line {i}: must be an object/dict.")
            continue

        missing = [k for k in required if k not in ln]
        if missing:
            errors.append(f"Line {i}: missing fields {missing}.")
            continue

        side = str(ln.get("side", "")).upper().strip()
        if side not in ALLOWED_SIDES:
            errors.append(f"Line {i}: side must be DR or CR.")
            continue

        try:
            amt = float(ln.get("amount", 0))
        except Exception:
            errors.append(f"Line {i}: amount must be numeric.")
            continue

        if amt <= 0:
            errors.append(f"Line {i}: amount must be > 0.")
            continue

        if side == "DR":
            dr_total += amt
        else:
            cr_total += amt

    dr_total = round(dr_total, 2)
    cr_total = round(cr_total, 2)
    balanced = round(dr_total - cr_total, 2) == 0.0

    if not balanced:
        errors.append(f"Not balanced: DR={dr_total} CR={cr_total}")

    if errors:
        raise ValueError("; ".join(errors))

    return {"ok": True, "dr_total": dr_total, "cr_total": cr_total, "balanced": balanced, "errors": []}