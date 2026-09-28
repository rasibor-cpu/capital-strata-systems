from decimal import Decimal
import pytest

from engine.commercial.collection_service import CollectionService, InvalidCollectionTransition
from engine.domain.collections import CollectionStatus, CollectionTransaction
from engine.ledger.ledger_store import LedgerStore


def collection(status=CollectionStatus.SETTLED):
    return CollectionTransaction(
        obligation_id="obl-provider-1", customer_id="cust-1", account_id="acct-1",
        amount=Decimal("100.00"), currency="CAD", idempotency_key="provider-key-1",
        status=status, settlement_reference="settle-1" if status == CollectionStatus.SETTLED else None,
    )


def test_provider_fee_is_balanced_and_exactly_once():
    ledger = LedgerStore()
    svc = CollectionService(ledger)
    c = collection()
    first = svc.post_provider_fee(c, Decimal("2.75"), "sandbox-provider")
    second = svc.post_provider_fee(c, Decimal("2.75"), "sandbox-provider")
    assert first.ledger_txn_id == second.ledger_txn_id
    assert sum(e.debit for e in first.entries) == Decimal("2.75")
    assert sum(e.credit for e in first.entries) == Decimal("2.75")
    assert first.txn_type == "PROVIDER_FEE"


def test_provider_fee_before_settlement_fails_closed():
    svc = CollectionService(LedgerStore())
    with pytest.raises(InvalidCollectionTransition):
        svc.post_provider_fee(collection(CollectionStatus.AUTHORIZED), Decimal("2.75"), "sandbox-provider")


@pytest.mark.parametrize("amount", [Decimal("0"), Decimal("-1"), Decimal("100.01")])
def test_invalid_provider_fee_amount_fails_closed(amount):
    svc = CollectionService(LedgerStore())
    with pytest.raises(ValueError):
        svc.post_provider_fee(collection(), amount, "sandbox-provider")
