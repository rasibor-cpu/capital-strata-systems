"""
REA Capital Trading Engine
Overdraft Guard (Hard Constraint)

Prevents postings that would breach approved overdraft limits.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class OverdraftProfile:
    approved_limit: int  # 0 means no overdraft allowed
    current_balance: int


def can_post_with_overdraft(
    profile: OverdraftProfile,
    posting_amount: int
) -> bool:
    """
    Returns True if posting is allowed under overdraft rules.
    Posting amount is assumed to be a debit (positive integer).
    """

    projected_balance = profile.current_balance - posting_amount

    # No overdraft allowed
    if profile.approved_limit <= 0:
        return projected_balance >= 0

    # Overdraft allowed but must not exceed approved limit
    return projected_balance >= -profile.approved_limit
