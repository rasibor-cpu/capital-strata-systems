"""
posting_approval.py — minimal approval rules scaffold

Purpose:
- Track this file in git.
- Provide a simple, deterministic approval decision function.

Safe defaults:
- If amount <= auto_approve_limit: approved
- Otherwise: pending approval
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class ApprovalDecision:
    status: str  # "approved" | "pending" | "rejected"
    reason: str
    required_role: Optional[str] = None


def decide_approval(
    amount: float,
    currency: str,
    *,
    auto_approve_limit: float = 2_000_000.0,
    required_role_over_limit: str = "admin",
) -> Dict[str, Any]:
    """
    Deterministic approval decision.
    """
    if amount < 0:
        d = ApprovalDecision(status="rejected", reason="amount cannot be negative")
        return d.__dict__

    if not currency or not isinstance(currency, str):
        d = ApprovalDecision(status="rejected", reason="currency is required")
        return d.__dict__

    if amount <= auto_approve_limit:
        d = ApprovalDecision(status="approved", reason=f"amount <= {auto_approve_limit:,.2f}")
        return d.__dict__

    d = ApprovalDecision(
        status="pending",
        reason=f"amount exceeds auto-approve limit ({auto_approve_limit:,.2f})",
        required_role=required_role_over_limit,
    )
    return d.__dict__
