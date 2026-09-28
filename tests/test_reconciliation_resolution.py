from decimal import Decimal
import pytest

from engine.commercial.reconciliation_service import ReconciliationService, SettlementEvidence
from engine.domain.collections import CollectionStatus, CollectionTransaction


def make_exception():
    c = CollectionTransaction(
        obligation_id="obl-x", customer_id="cust-1", account_id="acct-1",
        amount=Decimal("25.00"), currency="CAD", idempotency_key="x-key",
        status=CollectionStatus.SETTLED, provider_reference="p1",
        settlement_reference="s1", ledger_txn_id="l1",
    )
    svc = ReconciliationService()
    svc.reconcile(c, SettlementEvidence(c.collection_id, "p1", "s1", Decimal("24.00"), "CAD"))
    return svc, next(iter(svc.exceptions.values()))


def test_resolution_requires_attribution_and_reference():
    svc, item = make_exception()
    with pytest.raises(ValueError):
        svc.resolve_exception(item.exception_id, resolved_by="", resolution_reference="ticket-1")
    assert item.resolved_at is None


def test_resolution_is_attributed_and_removed_from_open_queue():
    svc, item = make_exception()
    resolved = svc.resolve_exception(item.exception_id, resolved_by="finance-controller", resolution_reference="ticket-1")
    assert resolved.resolved_at is not None
    assert resolved.resolved_by == "finance-controller"
    assert resolved.resolution_reference == "ticket-1"
    assert svc.open_exceptions() == []


def test_resolved_exception_is_immutable_except_idempotent_retry():
    svc, item = make_exception()
    first = svc.resolve_exception(item.exception_id, resolved_by="finance-controller", resolution_reference="ticket-1")
    second = svc.resolve_exception(item.exception_id, resolved_by="finance-controller", resolution_reference="ticket-1")
    assert second.resolved_at == first.resolved_at
    with pytest.raises(ValueError):
        svc.resolve_exception(item.exception_id, resolved_by="other-user", resolution_reference="ticket-2")
