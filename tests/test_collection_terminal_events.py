from decimal import Decimal
import pytest

from engine.commercial.collection_service import CollectionService, InvalidCollectionTransition
from engine.domain.collections import CollectionStatus, CollectionTransaction
from engine.ledger.ledger_store import LedgerStore


def settled_collection(service):
    c = CollectionTransaction(
        obligation_id="obl-terminal-1", customer_id="cust-1", account_id="acct-1",
        amount=Decimal("25.00"), currency="CAD", idempotency_key="terminal-key-1",
    )
    service.register(c)
    service.post_fee_obligation(c)
    service.transition(c, CollectionStatus.INITIATED, provider_reference="provider-1")
    service.transition(c, CollectionStatus.AUTHORIZED, provider_reference="provider-1")
    service.transition(c, CollectionStatus.SETTLED, settlement_reference="settle-1")
    service.post_settlement(c, "css-bank-cad")
    return c


@pytest.mark.parametrize("terminal", [
    CollectionStatus.REFUNDED, CollectionStatus.REVERSED, CollectionStatus.CHARGEBACK,
])
def test_terminal_adjustment_is_balanced_and_exactly_once(terminal):
    ledger = LedgerStore()
    service = CollectionService(ledger)
    c = settled_collection(service)
    service.transition(c, terminal)
    first = service.post_terminal_adjustment(c)
    second = service.post_terminal_adjustment(c)
    assert first.ledger_txn_id == second.ledger_txn_id
    assert sum(e.debit for e in first.entries) == sum(e.credit for e in first.entries)
    assert first.meta["economic_event_key"].endswith(f"{terminal.value}_FEE_ADJUSTMENT")


def test_terminal_adjustment_without_original_fee_fails_closed():
    ledger = LedgerStore()
    service = CollectionService(ledger)
    c = CollectionTransaction(
        obligation_id="obl-2", customer_id="cust-1", account_id="acct-1",
        amount=Decimal("25.00"), currency="CAD", idempotency_key="terminal-key-2",
        status=CollectionStatus.REFUNDED,
    )
    with pytest.raises(InvalidCollectionTransition):
        service.post_terminal_adjustment(c)
