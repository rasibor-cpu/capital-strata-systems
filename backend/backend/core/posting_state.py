"""
REA Capital Trading Engine
Posting State Core (Skeleton)

This module defines the canonical posting lifecycle used across:
- Treasury trades
- Customer account postings
- Overrides and approvals
- Facility / overdraft enforcement

NO execution logic lives here.
This file is structural and authoritative.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class PostingState(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    POSTED = "posted"
    REVERSED = "reversed"


class ApprovalLevel(str, Enum):
    NONE = "none"
    LEVEL_1 = "level_1"
    LEVEL_2 = "level_2"
    ADMIN = "admin"
    SUPER = "super"


@dataclass
class PostingContext:
    posting_id: str
    initiator_id: str
    amount: float
    currency: str

    current_state: PostingState
    required_approval: ApprovalLevel

    approver_id: Optional[str] = None
    approver_comment: Optional[str] = None
