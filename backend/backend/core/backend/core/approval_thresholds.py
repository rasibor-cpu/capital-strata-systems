"""
REA Capital Trading Engine
Approval Thresholds (Authoritative)

Defines approval routing bands for postings.
All amounts are in NGN by default, unless currency normalization is applied elsewhere.
"""

from dataclasses import dataclass
from typing import Optional
from .posting_state import ApprovalLevel


@dataclass(frozen=True)
class ThresholdBand:
    min_amount: int
    max_amount: Optional[int]  # None means no upper bound
    approval_level: ApprovalLevel


# Amount thresholds (NGN)
BANDS = [
    ThresholdBand(min_amount=0, max_amount=2_000_000, approval_level=ApprovalLevel.NONE),
    ThresholdBand(min_amount=2_000_001, max_amount=15_000_000, approval_level=ApprovalLevel.LEVEL_1),
    ThresholdBand(min_amount=15_000_001, max_amount=50_000_000, approval_level=ApprovalLevel.LEVEL_2),
    ThresholdBand(min_amount=50_000_001, max_amount=200_000_000, approval_level=ApprovalLevel.ADMIN),
    ThresholdBand(min_amount=200_000_001, max_amount=None, approval_level=ApprovalLevel.SUPER),
]


def required_approval_for_amount(amount: int) -> ApprovalLevel:
    """
    Returns the required approval level for a given NGN amount.
    """
    for band in BANDS:
        if band.max_amount is None:
            if amount >= band.min_amount:
                return band.approval_level
        else:
            if band.min_amount <= amount <= band.max_amount:
                return band.approval_level
    # Fallback (should never hit)
    return ApprovalLevel.SUPER
