"""
postings/submit_guard.py
-----------------------
Pre-submit enforcement logic for PostingTickets.

Purpose:
- Enforce mandatory governance checks BEFORE submit
- Keep PostingStore clean (no hidden side effects)
- UI / API must call this guard before store.submit(...)

Current enforcement:
1) Customer must be onboarded
2) Customer must have an APPROVED signature mandate

Future extensions:
- Daily limits
- Velocity checks
- Risk flags
"""

from typing import Optional

from postings.api import PostingStore
from postings.models import PostingTicket, PostingStatus
from posting_ledger import PostingLedger
from postings.mandates import MandateStore, MandateStatus


def ensure_can_submit(
    *,
    store: PostingStore,
    ticket_id: str,
    ledger: PostingLedger,
    mandates: MandateStore,
    customer_id: str,
) -> PostingTicket:
    """
    Raises ValueError if submission is not allowed.
    Returns ticket if allowed.
    """

    if not ticket_id or not ticket_id.strip():
        raise ValueError("ticket_id is required")

    if not customer_id or not customer_id.strip():
        raise ValueError("customer_id is required")

    t = store.get(ticket_id)

    if t.status != PostingStatus.DRAFT:
        raise ValueError("only DRAFT tickets can be submitted")

    # 1) Customer onboarding check
    if not ledger.is_customer_onboarded(customer_id):
        raise ValueError("customer not onboarded")

    # 2) Signature mandate check
    m = mandates.get_active_signature_mandate(customer_id)
    if m is None:
        raise ValueError("no APPROVED signature mandate on file")

    if m.status != MandateStatus.APPROVED:
        raise ValueError("signature mandate not approved")

    return t
