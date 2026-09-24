"""Fail-closed commercial collection domain models.

No provider credentials or live debit capability lives in this module.  It defines
immutable identifiers and state transitions used by provider adapters, accounting,
reconciliation, statements and receipts.
"""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, Any
import uuid


class CollectionStatus(str, Enum):
    OBLIGATION = "OBLIGATION"
    INITIATED = "INITIATED"
    AUTHORIZED = "AUTHORIZED"
    SETTLED = "SETTLED"
    FAILED = "FAILED"
    REVERSED = "REVERSED"
    REFUNDED = "REFUNDED"
    CHARGEBACK = "CHARGEBACK"


@dataclass(frozen=True)
class CustomerCommercialProfile:
    customer_id: str
    account_id: str
    fee_schedule_id: str
    currency: str
    provider_customer_token: Optional[str] = None
    payment_mandate_token: Optional[str] = None
    designated_settlement_account_id: Optional[str] = None
    collection_enabled: bool = False


@dataclass
class ChargeObligation:
    customer_id: str
    account_id: str
    currency: str
    gross_profit: Decimal
    eligible_profit: Decimal
    fee_amount: Decimal
    fee_schedule_id: str
    source_reference: str
    instrument: Optional[str] = None
    obligation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CollectionTransaction:
    obligation_id: str
    customer_id: str
    account_id: str
    amount: Decimal
    currency: str
    idempotency_key: str
    collection_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: CollectionStatus = CollectionStatus.OBLIGATION
    provider_reference: Optional[str] = None
    settlement_reference: Optional[str] = None
    initiated_at: Optional[datetime] = None
    settled_at: Optional[datetime] = None
    reconciled_at: Optional[datetime] = None
    ledger_txn_id: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def may_be_marked_paid(self) -> bool:
        """Paid requires both provider settlement and reconciliation evidence."""
        return (
            self.status == CollectionStatus.SETTLED
            and self.settled_at is not None
            and self.reconciled_at is not None
            and bool(self.settlement_reference)
            and bool(self.ledger_txn_id)
        )


@dataclass(frozen=True)
class TransactionReceipt:
    receipt_id: str
    collection_id: str
    customer_id: str
    account_id: str
    amount: Decimal
    currency: str
    status: str
    generated_at: datetime
    ledger_txn_id: str
    reconciliation_reference: str
    provider_reference: Optional[str] = None
    instrument: Optional[str] = None
    fee_schedule_id: Optional[str] = None
    reversal_of_receipt_id: Optional[str] = None
