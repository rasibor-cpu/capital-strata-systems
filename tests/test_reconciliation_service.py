from decimal import Decimal

from engine.commercial.reconciliation_service import (
    ReconciliationService, ReconciliationState, SettlementEvidence,
)
from engine.domain.collections import CollectionStatus, CollectionTransaction


def settled():
    return CollectionTransaction(
        obligation_id="obl-r1", customer_id="cust-1", account_id="acct-1",
        amount=Decimal("25.00"), currency="CAD", idempotency_key="recon-key",
        status=CollectionStatus.SETTLED, provider_reference="provider-1",
        settlement_reference="settle-1", ledger_txn_id="ledger-1",
    )


def evidence(**overrides):
    values = dict(collection_id="", provider_reference="provider-1",
                  settlement_reference="settle-1", amount=Decimal("25.00"), currency="CAD")
    values.update(overrides)
    return SettlementEvidence(**values)


def test_exact_settlement_evidence_matches():
    c = settled()
    svc = ReconciliationService()
    assert svc.reconcile(c, evidence(collection_id=c.collection_id)) == ReconciliationState.MATCHED
    assert not svc.exceptions


def test_amount_mismatch_enters_exception_queue_and_is_idempotent():
    c = settled()
    svc = ReconciliationService()
    bad = evidence(collection_id=c.collection_id, amount=Decimal("24.99"))
    assert svc.reconcile(c, bad) == ReconciliationState.EXCEPTION
    assert svc.reconcile(c, bad) == ReconciliationState.EXCEPTION
    assert len(svc.exceptions) == 1
    item = next(iter(svc.exceptions.values()))
    assert item.reason == "amount"
    assert item.expected == "25.00"
    assert item.observed == "24.99"


def test_unposted_collection_cannot_reconcile():
    c = settled()
    c.ledger_txn_id = None
    svc = ReconciliationService()
    assert svc.reconcile(c, evidence(collection_id=c.collection_id)) == ReconciliationState.EXCEPTION
    assert len(svc.exceptions) == 1
