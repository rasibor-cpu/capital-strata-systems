"""
REA Capital Trading Engine
Unified Approval Gate

Combines amount, overdraft, and currency guards into a single decision point.
"""

from typing import Optional
from core.posting_state import PostingState
from core.overdraft_guard import is_overdraft_allowed
from core.currency_guard import CurrencyContext, currencies_match
from core.approval_thresholds import required_approval_for_amount


def approval_required(
    amount: int,
    posting_state: PostingState,
    overdraft_allowed: bool,
    currency_ctx: CurrencyContext,
):
    """
    Returns required approval level or raises ValueError if hard rules fail.
    """

    if not currencies_match(currency_ctx):
        raise ValueError("Currency mismatch: approval denied")

    if not is_overdraft_allowed(posting_state, overdraft_allowed):
        raise ValueError("Overdraft not permitted")

    return required_approval_for_amount(amount)
