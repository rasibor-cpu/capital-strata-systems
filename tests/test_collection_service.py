from decimal import Decimal
import pytest

from engine.domain.collections import CollectionStatus, CollectionTransaction
from engine.ledger.ledger_store import LedgerStore
from engine.commercial.collection_service import (
    CollectionService,
    DuplicateCollectionConflict,
    InvalidCollectionTransition,
)


def make_collection(key="key-1"):
    return CollectionTransaction(
        obligation_id="obl-1",
        customer_id="cust-1",
        account_id="acct-1",
        amount=Decimal("25.00"),
        currency="CAD",
        idempotency_key=key,
    )


def test_registration_is_idempotent():
    svc = CollectionService(LedgerStore())
    first = svc.register(make_collection())
    second = svc.register(make_collection())
    assert second is first


def test_conflicting_idempotency_key_fails_closed():
    svc = CollectionService(LedgerStore())
    svc.register(make_collection())
    conflicting = make_collection()
    conflicting.amount = Decimal("26.00")
    with pytest.raises(DuplicateCollectionConflict):
        svc.register(conflicting)


def test_illegal_transition_fails_closed():
    svc = CollectionService(LedgerStore())
    c = svc.register(make_collection())
    with pytest.raises(InvalidCollectionTransition):
        svc.transition(c, CollectionStatus.SETTLED, settlement_reference="settle-1")


def test_fee_and_settlement_are_balanced_and_exactly_once():
    ledger = LedgerStore()
    svc = CollectionService(ledger)
    c = svc.register(make_collection())
    fee1 = svc.post_fee_obligation(c)
    fee2 = svc.post_fee_obligation(c)
    assert fee1.ledger_txn_id == fee2.ledger_txn_id

    svc.transition(c, CollectionStatus.INITIATED, provider_reference="provider-1")
    svc.transition(c, CollectionStatus.AUTHORIZED, provider_reference="provider-1")
    svc.transition(c, CollectionStatus.SETTLED, settlement_reference="settle-1")
    settle1 = svc.post_settlement(c, "css-bank-cad")
    settle2 = svc.post_settlement(c, "css-bank-cad")
    assert settle1.ledger_txn_id == settle2.ledger_txn_id
    assert len(ledger.transactions) == 2
    for txn in ledger.transactions.values():
        assert sum(e.debit for e in txn.entries) == sum(e.credit for e in txn.entries)
        assert all(e.ledger_txn_id == txn.ledger_txn_id for e in txn.entries)


def test_paid_gate_requires_reconciliation_after_settlement_posting():
    svc = CollectionService(LedgerStore())
    c = svc.register(make_collection())
    svc.transition(c, CollectionStatus.INITIATED, provider_reference="provider-1")
    svc.transition(c, CollectionStatus.AUTHORIZED, provider_reference="provider-1")
    svc.transition(c, CollectionStatus.SETTLED, settlement_reference="settle-1")
    svc.post_settlement(c, "css-bank-cad")
    assert not c.may_be_marked_paid
    svc.mark_reconciled(c, "recon-1")
    assert c.may_be_marked_paid
