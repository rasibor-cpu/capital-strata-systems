"""
posting_ledger.py — Customer Posting Ledger (Governance-Grade, Domain-Separated)
--------------------------------------------------------------------------------
Enhancements (LOCKED):
- Enforce onboarding: no postings without customer number
- ACCOUNT_OPEN requires SUPERVISOR+ approval
- Domain-separated system accounts:
    * TREASURY: SUSPENSE / SUNDRY
    * TRADING:  SUSPENSE / SUNDRY
- Backward compatibility for legacy SYS-SUSPENSE / SYS-SUNDRY IDs
- Append-only, audit-safe

Design intent:
- Clean separation of operational breaks by domain
- Regulator-friendly ageing and control reporting
"""

from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid


# -----------------------------
# Approval levels
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
    ledger_type: str            # CUSTOMER / TREASURY / TRADING / INTERNAL
    ledger_id: str
    domain: str                 # TREASURY / TRADING

    # Transaction context
    transaction_type: str       # ACCOUNT_OPEN / POSTING / TRANSFER / FX / ADJUSTMENT
    side: str                   # DR / CR
    currency: str
    notional: float
    fx_pair: Optional[str]
    price: Optional[float]
    value_date: Optional[str]
    booking_date: str
    description: str

    # Approval metadata
    approved_by: Optional[str]
    approval_level: Optional[str]


# -----------------------------
# Posting Ledger
# -----------------------------

class PostingLedger:
    def __init__(self):
        self.entries: List[PostingEntry] = []
        self.customers: Dict[str, CustomerRecord] = {}

        # Domain-separated SYSTEM accounts (authoritative)
        self._ensure_system_account(
            "SYS-SUSPENSE-TREASURY", "Treasury Suspense Account", "SUSP-TREAS-001"
        )
        self._ensure_system_account(
            "SYS-SUNDRY-TREASURY", "Treasury Sundry Account", "SUND-TREAS-001"
        )
        self._ensure_system_account(
            "SYS-SUSPENSE-TRADING", "Trading Suspense Account", "SUSP-TRAD-001"
        )
        self._ensure_system_account(
            "SYS-SUNDRY-TRADING", "Trading Sundry Account", "SUND-TRAD-001"
        )

        # Backward compatibility (legacy IDs)
        self._ensure_system_account(
            "SYS-SUSPENSE", "Legacy Suspense Account", "SUSP-LEGACY"
        )
        self._ensure_system_account(
            "SYS-SUNDRY", "Legacy Sundry Account", "SUND-LEGACY"
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
        level = (approval_level or "").upper().strip()
        if APPROVAL_ORDER.get(level, -1) < APPROVAL_ORDER["SUPERVISOR"]:
            raise ValueError("ACCOUNT_OPEN requires at least SUPERVISOR approval")

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

        # Ledger event for account opening
        self._append_entry(
            customer=rec,
            ledger_type="CUSTOMER",
            ledger_id=f"LEDGER-{account_ref}",
            domain="TREASURY",
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
        if customer_id in self.customers:
            return
        self.customers[customer_id] = CustomerRecord(
            customer_id=customer_id,
            customer_name=customer_name,
            account_ref=account_ref,
            customer_type="SYSTEM",
            opened_at=datetime.utcnow().isoformat(),
            approved_by="SYSTEM_BOOTSTRAP",
            approval_level="ADMIN",
        )

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
        domain: str,
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

        if not self.is_customer_onboarded(customer_id):
            raise ValueError("Customer not onboarded: customer_id must exist before postings")

        ttype = (transaction_type or "").upper().strip()
        if ttype == "ACCOUNT_OPEN":
            raise ValueError("Use open_customer_account() for ACCOUNT_OPEN transactions")

        dom = (domain or "").upper().strip()
        if dom not in ("TREASURY", "TRADING"):
            raise ValueError("domain must be TREASURY or TRADING")

        customer = self.customers[customer_id]

        return self._append_entry(
            customer=customer,
            ledger_type=ledger_type,
            ledger_id=ledger_id,
            domain=dom,
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
        domain: str,
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
            domain=domain,

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
    # Snapshots
    # -------------------------

    def snapshot(self) -> List[Dict[str, Any]]:
        return [asdict(e) for e in self.entries]

    def customers_snapshot(self) -> List[Dict[str, Any]]:
        return [asdict(c) for c in self.customers.values()]
