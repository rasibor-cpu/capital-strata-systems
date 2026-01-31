"""
postings/maker_screen.py
------------------------
Phase 10 — Maker Screen orchestration (UI-facing logic).

Responsibilities:
- Create a DRAFT ticket from UI input
- Compute required approval level (limits)
- Show mandate status summary
- Provide submit-guard preview (can_submit + reason), without mutating ticket state

This module is UI-agnostic: works for Web/Android/CLI.
"""

from decimal import Decimal
from typing import Optional

from postings.api import PostingStore
from postings.maker_ticket import MakerTicketInput, create_maker_ticket
from postings.mandates import MandateStore, MandateStatus
from postings.limits import ThresholdBands, required_approval_level_for_amount
from posting_ledger import PostingLedger
from postings.screen_contracts import (
    MakerCreateTicketResponse,
    GuardStatus,
    MandateStatusView,
    ApprovalLevelView,
)


def _mandate_view(mandates: MandateStore, customer_id: str) -> MandateStatusView:
    m = mandates.get_active_signature_mandate(customer_id)
    if m is None:
        return MandateStatusView(
            customer_id=customer_id,
            mandate_exists=False,
            mandate_status="NONE",
            signing_rule=None,
            specimen_count=None,
        )
    return MandateStatusView(
        customer_id=customer_id,
        mandate_exists=True,
        mandate_status=m.status.value,
        signing_rule=m.signing_rule.value,
        specimen_count=m.specimen_count,
    )


def _guard_preview(
    *,
    ledger: PostingLedger,
    mandates: MandateStore,
    customer_id: str,
) -> GuardStatus:
    # Mirror the submit_guard checks as a non-throwing preview.
    if not ledger.is_customer_onboarded(customer_id):
        return GuardStatus(can_submit=False, reason="customer not onboarded")

    m = mandates.get_active_signature_mandate(customer_id)
    if m is None:
        return GuardStatus(can_submit=False, reason="no APPROVED signature mandate on file")
    if m.status != MandateStatus.APPROVED:
        return GuardStatus(can_submit=False, reason="signature mandate not approved")

    return GuardStatus(can_submit=True, reason=None)


def create_ticket_for_maker_screen(
    *,
    store: PostingStore,
    ledger: PostingLedger,
    mandates: MandateStore,
    customer_id: str,
    maker_input: MakerTicketInput,
    bands: Optional[ThresholdBands] = None,
) -> MakerCreateTicketResponse:
    """
    UI entry point for Maker screen: returns a full response model.

    Important:
    - Creates ticket DRAFT
    - Does not submit
    """
    if not customer_id or not customer_id.strip():
        raise ValueError("customer_id is required")

    b = bands or ThresholdBands()

    # Create draft ticket
    t = create_maker_ticket(store, maker_input, customer_id=customer_id)

    # Compute required approval based on amount
    # Note: t.amount is Decimal already
    required_level = required_approval_level_for_amount(Decimal(str(t.amount)), b)

    approval_view = ApprovalLevelView(
        required_level=required_level,
        current_level="MAKER",
        is_satisfied=(required_level == "AUTO"),
    )

    mandate_view = _mandate_view(mandates, customer_id)
    guard = _guard_preview(ledger=ledger, mandates=mandates, customer_id=customer_id)

    return MakerCreateTicketResponse(
        ticket_id=t.ticket_id,
        status=t.status.value,
        approval_view=approval_view,
        mandate_view=mandate_view,
        guard=guard,
    )
