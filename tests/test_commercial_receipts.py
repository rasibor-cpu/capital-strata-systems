from datetime import datetime
from decimal import Decimal
import pytest

from engine.domain.collections import CollectionStatus, CollectionTransaction
from engine.reporting.commercial_receipts import (
    ReceiptNotReconciledError,
    generate_paid_receipt,
)


def collection(**overrides):
    values = dict(
        obligation_id="obl-1",
        customer_id="cust-1",
        account_id="acct-USD-1",
        amount=Decimal("125.50"),
        currency="USD",
        idempotency_key="fee:cust-1:trade-9",
    )
    values.update(overrides)
    return CollectionTransaction(**values)


def test_paid_receipt_fails_closed_before_settlement():
    with pytest.raises(ReceiptNotReconciledError):
        generate_paid_receipt(collection())


def test_settlement_without_reconciliation_is_not_paid():
    c = collection(
        status=CollectionStatus.SETTLED,
        settled_at=datetime.utcnow(),
        settlement_reference="settle-1",
        ledger_txn_id="ledger-1",
    )
    with pytest.raises(ReceiptNotReconciledError):
        generate_paid_receipt(c)


def test_reconciled_settlement_can_generate_paid_receipt():
    now = datetime.utcnow()
    c = collection(
        status=CollectionStatus.SETTLED,
        provider_reference="provider-1",
        settled_at=now,
        reconciled_at=now,
        settlement_reference="settle-1",
        ledger_txn_id="ledger-1",
    )
    receipt = generate_paid_receipt(c, instrument="AAPL", fee_schedule_id="fees-v1")
    assert receipt.status == "PAID"
    assert receipt.amount == Decimal("125.50")
    assert receipt.currency == "USD"
    assert receipt.ledger_txn_id == "ledger-1"
    assert receipt.reconciliation_reference == "settle-1"
