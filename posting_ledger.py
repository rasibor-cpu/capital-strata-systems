"""
posting_ledger.py — Customer Posting Ledger (Governance-Grade)
--------------------------------------------------------------
Purpose:
- Enforce onboarding: customer must exist (have customer number) before postings
- Enforce approvals: ACCOUNT_OPEN requires at least SUPERVISOR approval
- Support system accounts: SUSPENSE and SUNDRY
- Record customer-related postings (DR/CR, FX, transfers, adjustments)
- Provide full customer + ledger + transaction context for breach reporting

Design:
- Append-only ledger entries
- Deterministic, in-memory (demo-grade). Production would persist.
- No execution / no settlement
"""

from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid


# -----------------------------
# Enums / levels (string-based)
# -----------------------------
APPROVAL_ORDER = {
    "AUTO": 0,
    "USER": 1,
    "SUPERVISOR": 2,
    "MANAGER": 3,
    "ADMIN": 4,
    "SUPER": 5,
}


# -----------------------------
# Customer Registry
# -----------------------------

@dataclass
class CustomerRecord:
    customer_id: str
    customer_name: str
    account_ref: str
    customer_type: str          # CUSTOMER / SYSTEM
    opened_at: str
    approved_by: Optional[str]
    approval_level: Optional[str]


# -----------------------------
# Posting Entry
# -----------------------------

@dataclass
class PostingEntry:
    entry_id: str

    # Customer context
    customer_id: str
    customer_name: str
    account_ref: str
    customer_type: str          # CUSTOMER / SYSTEM

    # Ledger context
    ledger_type: str            # CUSTOMER / TREASURY / INTERNAL
    ledger_id: str

    # Transaction context
    transaction_type: str       # ACCOUNT_OPEN / POSTING / TRANSFER / FX / ADJUSTMENT
    side: str                   # DR / CR
    currency: str               # e.g. USD, NGN, EUR
    notional: float
    fx_pair: Optional[str]      # e.g. USDNGN (if FX)
    price: Optional[float]
    value_date: Optional[str]
    booking_date: str
    description: str

    # Approval metadata (where applicable)
    approved_by: Optional[str]
    approval_level: Optional[str]


# -----------------------------
# Posting Ledger
# -----------------------------

class PostingLedger:
    def __init__(self):
        self.entries: List[PostingEntry] = []
        self.customers: Dict[str, CustomerRecord] = {}

        # Pre-board system accounts (required by your governance rule)
        self._ensure_system_account(
            customer_id="SYS-SUSPENSE",
            customer_name="Suspense Account",
            account_ref="SUSPENSE-001",
        )
        self._ensure_system_account(
            customer_id="SYS-SUNDRY",
            customer_name="Sundry Account",
            account_ref="SUNDRY-001",
        )

    # -------------------------
    # Customer onboarding
    # -------------------------

    def open_customer_account(
        self,
        customer_name: str,
        account_ref: str,
        approved_by: str,
        approval_level: str,
        customer_id: Optional[str] = None,
    ) -> CustomerRecord:
        """
        Opens/boards a customer onto the system and issues a customer number.

        Governance:
        - ACCOUNT_OPEN requires at least SUPERVISOR approval.
        """
        level = (approval_level or "").upper().strip()
        if APPROVAL_ORDER.get(level, -1) < APPROVAL_ORDER["SUPERVISOR"]:
            raise ValueError("ACCOUNT_OPEN requires at least SUPERVISOR approval_level")

        cid = customer_id or f"CUST-{uuid.uuid4().hex[:8].upper()}"
        rec = CustomerRecord(
            customer_id=cid,
            customer_name=customer_name,
            account_ref=account_ref,
            customer_type="CUSTOMER",
            opened_at=datetime.utcnow().isoformat(),
            approved_by=approved_by,
            approval_level=level,
        )
        self.customers[cid] = rec

        # Record the onboarding as a ledger event (append-only)
        self._append_entry(
            customer=rec,
            ledger_type="CUSTOMER",
            ledger_id=f"LEDGER-{account_ref}",
            transaction_type="ACCOUNT_OPEN",
            side="CR",
            currency="N/A",
            notional=0.0,
            description="Customer onboarded / account opened",
            fx_pair=None,
            price=None,
            value_date=None,
            approved_by=approved_by,
            approval_level=level,
        )
        return rec

    def _ensure_system_account(self, customer_id: str, customer_name: str, account_ref: str) -> None:
        """
        System accounts are considered pre-approved internal constructs.
        """
        if customer_id in self.customers:
            return
        rec = CustomerRecord(
            customer_id=customer_id,
            customer_name=customer_name,
            account_ref=account_ref,
            customer_type="SYSTEM",
            opened_at=datetime.utcnow().isoformat(),
            approved_by="SYSTEM_BOOTSTRAP",
            approval_level="ADMIN",
        )
        self.customers[customer_id] = rec

    def is_customer_onboarded(self, customer_id: str) -> bool:
        return customer_id in self.customers

    # -------------------------
    # Postings
    # -------------------------

    def post(
        self,
        customer_id: str,
        ledger_type: str,
        ledger_id: str,
        transaction_type: str,
        side: str,
        currency: str,
        notional: float,
        description: str,
        fx_pair: Optional[str] = None,
        price: Optional[float] = None,
        value_date: Optional[str] = None,
        approved_by: Optional[str] = None,
        approval_level: Optional[str] = None,
    ) -> PostingEntry:
        """
        Posts a transaction for an onboarded customer or system account.

        Governance:
        - customer_id must exist (onboarded) BEFORE any posting is allowed.
        - ACCOUNT_OPEN must be done via open_customer_account() (supervisor-approved).
        """
        if not self.is_customer_onboarded(customer_id):
            raise ValueError("Customer not onboarded: customer_id must exist before postings")

        ttype = (transaction_type or "").upper().strip()
        if ttype == "ACCOUNT_OPEN":
            raise ValueError("Use open_customer_account() for ACCOUNT_OPEN transactions")

        customer = self.customers[customer_id]

        return self._append_entry(
            customer=customer,
            ledger_type=ledger_type,
            ledger_id=ledger_id,
            transaction_type=ttype,
            side=side,
            currency=currency,
            notional=notional,
            description=description,
            fx_pair=fx_pair,
            price=price,
            value_date=value_date,
            approved_by=approved_by,
            approval_level=(approval_level.upper().strip() if approval_level else None),
        )

    # -------------------------
    # Internal append
    # -------------------------

    def _append_entry(
        self,
        customer: CustomerRecord,
        ledger_type: str,
        ledger_id: str,
        transaction_type: str,
        side: str,
        currency: str,
        notional: float,
        description: str,
        fx_pair: Optional[str],
        price: Optional[float],
        value_date: Optional[str],
        approved_by: Optional[str],
        approval_level: Optional[str],
    ) -> PostingEntry:
        entry = PostingEntry(
            entry_id=str(uuid.uuid4()),

            customer_id=customer.customer_id,
            customer_name=customer.customer_name,
            account_ref=customer.account_ref,
            customer_type=customer.customer_type,

            ledger_type=ledger_type,
            ledger_id=ledger_id,

            transaction_type=transaction_type,
            side=side,
            currency=currency,
            notional=float(notional),
            fx_pair=fx_pair,
            price=price,
            value_date=value_date,
            booking_date=datetime.utcnow().isoformat(),
            description=description,

            approved_by=approved_by,
            approval_level=approval_level,
        )
        self.entries.append(entry)
        return entry

    # -------------------------
    # Snapshot / export
    # -------------------------

    def snapshot(self) -> List[Dict[str, Any]]:
        return [asdict(e) for e in self.entries]

    def customers_snapshot(self) -> List[Dict[str, Any]]:
        return [asdict(c) for c in self.customers.values()]
