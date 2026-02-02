"""
Checker Screen Builder
----------------------
Phase 11 — Checker screen decision logic (UI-agnostic).

Purpose:
- Determine if a checker at a given approval level can approve/post a ticket.
- Enforce mandate requirement for customer postings.
- Compute required approval level from amount thresholds (LOCKED governance).

Important:
- This module has NO side effects.
- It does not approve, reject, or post anything.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from postings.limits import ThresholdBands, required_approval_level_for_amount, is_level_sufficient
from postings.mandates import MandateStore, MandateStatus
from postings.models import PostingType


@dataclass(frozen=True)
class CheckerDecision:
    allowed: bool
    required_level: str
    approver_level: str
    reason: Optional[str] = None


def build_checker_decision(
    *,
    mandates: MandateStore,
    customer_id: str,
    posting_type: PostingType,
    amount: Decimal,
    approver_level: str,
    bands: Optional[ThresholdBands] = None,
) -> CheckerDecision:
    """
    Decide if checker can proceed with approval/posting.

    Rules:
    1) Approval level must satisfy required level from amount thresholds
    2) Customer must have an APPROVED signature mandate (current enum)
    """

    b = bands or ThresholdBands()

    required_level = required_approval_level_for_amount(amount, b)
    got_level = (approver_level or "").strip().upper()

    # 1) Approval authority
    if not is_level_sufficient(required_level, got_level):
        return CheckerDecision(
            allowed=False,
            required_level=required_level,
            approver_level=got_level,
            reason="Insufficient approval level for amount",
        )

    # 2) Signature mandate enforcement (customer postings)
    mandate = mandates.get_active_signature_mandate(customer_id)
    if mandate is None:
        return CheckerDecision(
            allowed=False,
            required_level=required_level,
            approver_level=got_level,
            reason="No signature mandate on file",
        )

    if mandate.status != MandateStatus.APPROVED:
        return CheckerDecision(
            allowed=False,
            required_level=required_level,
            approver_level=got_level,
            reason="Signature mandate not approved",
        )

    # Pass
    return CheckerDecision(
        allowed=True,
        required_level=required_level,
        approver_level=got_level,
        reason=None,
    )
