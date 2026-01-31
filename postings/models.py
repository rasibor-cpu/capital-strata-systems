"""
postings/models.py
------------------
Core posting-domain models for REA Capital Trading Engine.

These models are UI-agnostic and API-first.
They define maker tickets, approval workflow, and ledger-ready postings.

Authoritative baseline for Posting Screens (v1).
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
import uuid


# -----------------------------
# Enums
# -----------------------------

class PostingStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    POSTED = "POSTED"


class PostingType(str, Enum):
    JOURNAL = "JOURNAL"
    FX = "FX"
    CASH = "CASH"
    ADJUSTMENT = "ADJUSTMENT"


# -----------------------------
# Core Models
# -----------------------------

@dataclass
class PostingTicket:
    """
    Maker ticket representing a financial posting request.
    This is the unit that flows through maker → checker → ledger.
    """

    ticket_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    posting_type: PostingType = PostingType.JOURNAL

    # Amounts
    amount: Decimal = Decimal("0.00")
    currency: str = "USD"

    # Ledger intent
    debit_account: str = ""
    credit_account: str = ""

    # Workflow
    status: PostingStatus = PostingStatus.DRAFT
    maker_user: str = ""
    approver_user: Optional[str] = None

    # Audit
    description: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    posted_at: Optional[datetime] = None

    # Controls
    approval_level_required: int = 0  # 0 = none, 1 = L1, 2 = L2, etc.

    def submit(self) -> None:
        if self.status != PostingStatus.DRAFT:
            raise ValueError("Only DRAFT tickets can be submitted")
        self.status = PostingStatus.SUBMITTED
        self.submitted_at = datetime.utcnow()

    def approve(self, approver: str) -> None:
        if self.status != PostingStatus.SUBMITTED:
            raise ValueError("Only SUBMITTED tickets can be approved")
        self.status = PostingStatus.APPROVED
        self.approver_user = approver
        self.approved_at = datetime.utcnow()

    def reject(self, approver: str) -> None:
        if self.status != PostingStatus.SUBMITTED:
            raise ValueError("Only SUBMITTED tickets can be rejected")
        self.status = PostingStatus.REJECTED
        self.approver_user = approver

    def mark_posted(self) -> None:
        if self.status != PostingStatus.APPROVED:
            raise ValueError("Only APPROVED tickets can be posted to ledger")
        self.status = PostingStatus.POSTED
        self.posted_at = datetime.utcnow()
