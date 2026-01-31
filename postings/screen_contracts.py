"""
screen_contracts.py
-------------------------------------------------
Phase 10 — Posting Screens (UI Contracts)

Purpose:
- Define authoritative request/response payloads
- UI-agnostic (Web / Mobile / API)
- No business logic
- No validation side-effects

Status:
- GOVERNANCE LOCKED
- READ-ONLY interfaces to Posting Engine
"""

from dataclasses import dataclass
from typing import Optional, List, Dict
from decimal import Decimal
from enum import Enum


# -----------------------------
# Screen Roles
# -----------------------------

class ScreenRole(str, Enum):
    MAKER = "MAKER"
    CHECKER = "CHECKER"
    SUPERVISOR = "SUPERVISOR"
    ADMIN = "ADMIN"
    SUPER = "SUPER"


# -----------------------------
# Common UI Status Flags
# -----------------------------

@dataclass(frozen=True)
class GuardStatus:
    can_submit: bool
    reason: Optional[str] = None


@dataclass(frozen=True)
class MandateStatusView:
    customer_id: str
    mandate_exists: bool
    mandate_status: str        # PENDING / ACTIVE / REVOKED
    signing_rule: Optional[str]
    specimen_count: Optional[int]


@dataclass(frozen=True)
class ApprovalLevelView:
    required_level: str        # AUTO / USER / SUPERVISOR / SUPER
    current_level: str
    is_satisfied: bool


# -----------------------------
# MAKER SCREEN
# -----------------------------

@dataclass(frozen=True)
class MakerCreateTicketRequest:
    customer_id: str
    posting_type: str          # JOURNAL / TRANSFER / FX
    amount: Decimal
    currency: str
    debit_account: str
    credit_account: str
    description: str


@dataclass(frozen=True)
class MakerCreateTicketResponse:
    ticket_id: str
    status: str                # DRAFT
    approval_view: ApprovalLevelView
    mandate_view: MandateStatusView
    guard: GuardStatus


# -----------------------------
# CHECKER SCREEN
# -----------------------------

@dataclass(frozen=True)
class PendingApprovalItem:
    ticket_id: str
    customer_id: str
    amount: Decimal
    currency: str
    posting_type: str
    required_approval_level: str
    submitted_by: str
    submitted_at: str


@dataclass(frozen=True)
class CheckerApprovalRequest:
    ticket_id: str
    action: str                # APPROVE / REJECT
    checker_user: str


@dataclass(frozen=True)
class CheckerApprovalResponse:
    ticket_id: str
    new_status: str
    approved_by: Optional[str]
    approval_level: Optional[str]


# -----------------------------
# OVERSIGHT SCREENS
# -----------------------------

@dataclass(frozen=True)
class LedgerEntryView:
    entry_id: str
    side: str                  # DR / CR
    ledger_id: str
    currency: str
    amount: Decimal
    booking_date: str
    value_date: Optional[str]
    description: str


@dataclass(frozen=True)
class AuditTrailItem:
    event_time: str
    actor: str
    action: str
    details: Dict[str, str]


@dataclass(frozen=True)
class TicketAuditView:
    ticket_id: str
    current_status: str
    audit_trail: List[AuditTrailItem]
    ledger_entries: List[LedgerEntryView]
