from enum import Enum
from typing import Set

from .approval_gate import ApprovalLevel


class UserRole(Enum):
    MAKER = "maker"
    CHECKER = "checker"
    ADMIN = "admin"
    SUPER = "super"


def can_user_approve(
    *,
    user_role: UserRole,
    user_approval_level: ApprovalLevel,
    required_level: ApprovalLevel,
    is_maker: bool,
    higher_approvers_present: Set[ApprovalLevel],
) -> bool:
    """
    Enforces maker–checker and one-up / two-up approval rules.

    Rules:
    - Maker can NEVER approve own transaction
    - User must meet or exceed required approval level
    - Admin can approve up to ADMIN band
    - SUPER can approve anything
    - If SUPER unavailable, requires at least two higher approvers
    """

    # Rule 1: Maker cannot approve own transaction
    if is_maker:
        return False

    # Rule 2: SUPER override
    if user_role == UserRole.SUPER:
        return True

    # Rule 3: Approval level check
    if user_approval_level.value < required_level.value:
        return False

    # Rule 4: Admin ceiling
    if required_level == ApprovalLevel.SUPER:
        # SUPER required — fallback only allowed if two higher levels exist
        return len(higher_approvers_present) >= 2

    return True
