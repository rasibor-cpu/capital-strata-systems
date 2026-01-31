"""
Maker Screen Builder
--------------------
Creates a maker-facing screen context with governance checks.

LOCKED principles:
- Dependencies injected explicitly (no hidden globals)
- Customer must be onboarded
- Signature mandate must exist and be APPROVED (current enum)
- Approval level derived from limits
- Zero side-effects (builder only)
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from postings.models import PostingType
from postings.limits import ThresholdBands, required_approval_level_for_amount
from postings.mandates import MandateStore, MandateStatus
from postings.api import PostingStore
from posting_ledger import PostingLedger


# -----------------------------
# Output DTOs (minimal, stable)
# -----------------------------

@dataclass
class MakerScreenGuard:
    can_submit: bool
    required_level: str
    reason: Optional[str] = None


@dataclass
class MakerScreenResponse:
    status: str
    guard: MakerScreenGuard


# -----------------------------
# Builder
# -----------------------------

def build_maker_screen(
    *,
    store: PostingStore,
    ledger: PostingLedger,
    mandates: MandateStore,
    customer_id: str,
    posting_type: PostingType,
    amount: Decimal,
    currency: str,
    debit_account: str,
    credit_account: str,
    maker_user: str,
    description: str,
) -> MakerScreenResponse:
    """
    Pure builder: evaluates governance and returns a screen guard.
    Does NOT create or submit tickets.
    """

    # 1) Customer must be onboarded
    if not ledger.is_customer_onboarded(customer_id):
        return MakerScreenResponse(
            status="BLOCKED",
            guard=MakerScreenGuard(
                can_submit=False,
                required_level="N/A",
                reason="Customer not onboarded",
            ),
        )

    # 2) Signature mandate must exist and be APPROVED
    mandate = mandates.get_active_signature_mandate(customer_id)
    if mandate is None:
        return MakerScreenResponse(
            status="BLOCKED",
            guard=MakerScreenGuard(
                can_submit=False,
                required_level="N/A",
                reason="No signature mandate on file",
            ),
        )

    if mandate.status != MandateStatus.APPROVED:
        return MakerScreenResponse(
            status="BLOCKED",
            guard=MakerScreenGuard(
                can_submit=False,
                required_level="N/A",
                reason="Signature mandate not approved",
            ),
        )

    # 3) Determine approval level from limits
    bands = ThresholdBands()
    required_level = required_approval_level_for_amount(amount, bands)

    return MakerScreenResponse(
        status="DRAFT",
        guard=MakerScreenGuard(
            can_submit=True,
            required_level=required_level,
            reason=None,
        ),
    )
