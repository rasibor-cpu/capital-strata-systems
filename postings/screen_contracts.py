"""
screen_contracts.py
---------------------------------------------------------
Posting Screens – Backend Screen Contracts (LOCKED)

Purpose:
- Define UI-facing, immutable screen contracts
- Enforce governance at the boundary
- Zero side effects, zero persistence
- Safe for mobile, web, API, or desktop UI

Design principles:
- UI never infers rules
- Backend declares truth
- Read-only DTOs
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional, Dict, Any
from datetime import datetime

# ----------------------------
# Shared primitives
# ----------------------------

@dataclass(frozen=True)
class ScreenError:
    code: str
    message: str
    blocking: bool = True


@dataclass(frozen=True)
class ScreenWarning:
    code: str
    message: str


@dataclass(frozen=True)
class ScreenApprovalInfo:
    required_level: str
    approver_roles: List[str]
    auto_allowed: bool


# ----------------------------
# Maker Ticket Screen
# ----------------------------

@dataclass(frozen=True)
class MakerTicketInputView:
    posting_type: str
    amount: Decimal
    currency: str
    debit_account: str
    credit_account: str
    description: str


@dataclass(frozen=True)
class MakerTicketGuardView:
    can_submit: bool
    approval: ScreenApprovalInfo
    mandate_status: str
    missing_requirements: List[str]
    warnings: List[ScreenWarning]
    errors: List[ScreenError]


@dataclass(frozen=True)
class MakerTicketScreen:
    ticket_id: Optional[str]
    input: MakerTicketInputView
    guard: MakerTicketGuardView
    status: str
    created_at: Optional[datetime]


# ----------------------------
# Approval Queue Screen
# ----------------------------

@dataclass(frozen=True)
class ApprovalQueueItem:
    ticket_id: str
    customer_id: str
    amount: Decimal
    currency: str
    posting_type: str
    required_level: str
    submitted_at: datetime
    risk_flags: List[str]


@dataclass(frozen=True)
class ApprovalQueueScreen:
    viewer_role: str
    pending_items: List[ApprovalQueueItem]
    can_approve: bool
    as_of: datetime


# ----------------------------
# Ticket Detail Screen
# ----------------------------

@dataclass(frozen=True)
class AuditEventView:
    event: str
    actor: str
    timestamp: datetime
    metadata: Dict[str, Any]


@dataclass(frozen=True)
class LedgerPreviewLine:
    side: str           # DR / CR
    account: str
    currency: str
    amount: Decimal


@dataclass(frozen=True)
class TicketDetailScreen:
    ticket_id: str
    customer_id: str
    status: str
    posting_type: str
    amount: Decimal
    currency: str

    maker_user: str
    approver_user: Optional[str]
    approval_level: Optional[str]

    mandates_verified: bool
    signatures_required: int
    signatures_present: int

    ledger_preview: List[LedgerPreviewLine]
    audit_trail: List[AuditEventView]

    created_at: datetime
    submitted_at: Optional[datetime]
    approved_at: Optional[datetime]
    posted_at: Optional[datetime]


# ----------------------------
# Contract versioning
# ----------------------------

SCREEN_CONTRACT_VERSION = "1.0.0"
SCREEN_CONTRACT_LOCKED = True
