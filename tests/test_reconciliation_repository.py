from decimal import Decimal

from engine.commercial.reconciliation_repository import ReconciliationRepository
from engine.commercial.reconciliation_service import ReconciliationService, SettlementEvidence
from engine.domain.collections import CollectionStatus, CollectionTransaction


def settled():
    return CollectionTransaction(
        obligation_id="obl-persist", customer_id="cust-1", account_id="acct-1",
        amount=Decimal("25.00"), currency="CAD", idempotency_key="recon-persist-key",
        status=CollectionStatus.SETTLED, provider_reference="provider-1",
        settlement_reference="settle-1", ledger_txn_id="ledger-1",
    )


def bad_evidence(c):
    return SettlementEvidence(
        collection_id=c.collection_id, provider_reference="provider-1",
        settlement_reference="settle-1", amount=Decimal("24.99"), currency="CAD",
    )


def test_exception_survives_service_restart(tmp_path):
    repo = ReconciliationRepository(str(tmp_path / "commercial.sqlite3"))
    c = settled()
    first = ReconciliationService(repo)
    first.reconcile(c, bad_evidence(c))
    item = first.open_exceptions()[0]

    restarted = ReconciliationService(ReconciliationRepository(str(tmp_path / "commercial.sqlite3")))
    open_items = restarted.open_exceptions()
    assert len(open_items) == 1
    assert open_items[0].exception_id == item.exception_id
    assert open_items[0].reason == "amount"


def test_resolution_survives_restart_and_history_is_retained(tmp_path):
    db = str(tmp_path / "commercial.sqlite3")
    repo = ReconciliationRepository(db)
    c = settled()
    svc = ReconciliationService(repo)
    svc.reconcile(c, bad_evidence(c))
    item = svc.open_exceptions()[0]
    svc.resolve_exception(
        item.exception_id,
        resolved_by="finance-controller",
        resolution_reference="ticket-100",
    )

    restarted_repo = ReconciliationRepository(db)
    restarted = ReconciliationService(restarted_repo)
    assert restarted.open_exceptions() == []
    history = restarted_repo.list_all()
    assert len(history) == 1
    assert history[0].exception_id == item.exception_id
    assert history[0].resolved_by == "finance-controller"
    assert history[0].resolution_reference == "ticket-100"
    assert history[0].resolved_at is not None


def test_duplicate_mismatch_is_exactly_once_across_restart(tmp_path):
    db = str(tmp_path / "commercial.sqlite3")
    c = settled()
    evidence = bad_evidence(c)
    first = ReconciliationService(ReconciliationRepository(db))
    first.reconcile(c, evidence)

    second_repo = ReconciliationRepository(db)
    second = ReconciliationService(second_repo)
    second.reconcile(c, evidence)
    assert len(second_repo.list_all()) == 1
