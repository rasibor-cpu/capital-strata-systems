"""Commercial history, statements and receipts: durable, deterministic, honest.

A statement or receipt must never present money as paid without settlement
and reconciliation evidence, and terminal events (refund, reversal,
chargeback) must add history rather than erase the original settlement.
"""
import sqlite3
from datetime import datetime
from decimal import Decimal

import pytest

from engine.commercial.collection_history import CollectionHistoryRepository
from engine.commercial.collection_repository import CollectionRepository
from engine.commercial.collection_service import CollectionService
from engine.domain.collections import CollectionStatus, CollectionTransaction
from engine.ledger.ledger_store import LedgerStore
from engine.reporting.commercial_receipts import (
    ReceiptNotReconciledError,
    generate_adjustment_receipt,
    generate_paid_receipt,
)
from engine.reporting.commercial_statements import build_statement


@pytest.fixture
def db(tmp_path):
    return str(tmp_path / "commercial.sqlite3")


def _collection(key, amount="100.00", customer="cust-1", currency="USD"):
    return CollectionTransaction(
        obligation_id=f"obl-{key}", customer_id=customer, account_id=f"acct-{customer}",
        amount=Decimal(amount), currency=currency, idempotency_key=f"fee:{key}",
    )


def _service(db):
    return CollectionService(LedgerStore(), history=CollectionHistoryRepository(db))


def _terminal_time(service, c):
    event = [e for e in service.history.history(c.collection_id) if e.to_status == c.status.value][0]
    return datetime.fromisoformat(event.occurred_at)


def _settle(service, c, reconcile=True):
    key = c.obligation_id.removeprefix("obl-")
    service.register(c)
    service.post_fee_obligation(c)
    service.transition(c, CollectionStatus.INITIATED, provider_reference=f"prov-{key}")
    service.transition(c, CollectionStatus.AUTHORIZED, provider_reference=f"prov-{key}")
    service.transition(c, CollectionStatus.SETTLED, settlement_reference=f"set-{key}")
    service.post_settlement(c, "settle-acct")
    if reconcile:
        service.mark_reconciled(c, f"recon-{key}")
    return c


# --- lifecycle history -------------------------------------------------------

def test_terminal_event_adds_history_without_erasing_settlement(db):
    service = _service(db)
    repo = CollectionRepository(db)
    c = _settle(service, _collection("a"))
    repo.save(c)
    service.transition(c, CollectionStatus.REFUNDED)
    service.post_terminal_adjustment(c)
    repo.save(c)

    restarted = CollectionHistoryRepository(db)
    timeline = [(e.to_status, e.from_status) for e in restarted.history(c.collection_id)]
    assert timeline == [
        ("INITIATED", "OBLIGATION"), ("AUTHORIZED", "INITIATED"), ("SETTLED", "AUTHORIZED"),
        ("RECONCILED", "SETTLED"), ("REFUNDED", "SETTLED"),
    ]
    settled = [e for e in restarted.history(c.collection_id) if e.to_status == "SETTLED"][0]
    assert settled.settlement_reference == "set-a" and settled.occurred_at
    reloaded = repo.get_by_idempotency_key("fee:a")
    assert reloaded.status == CollectionStatus.REFUNDED
    assert reloaded.settlement_reference == "set-a" and reloaded.settled_at is not None


def test_history_is_append_only_and_replay_safe(db):
    service = _service(db)
    c = _settle(service, _collection("b"))
    before = service.history.history(c.collection_id)
    service.transition(c, CollectionStatus.SETTLED)          # no-op transition
    service.mark_reconciled(c, "recon-b")                    # replay
    assert service.history.history(c.collection_id) == before
    conn = sqlite3.connect(db)
    for sql in ("UPDATE commercial_collection_events SET to_status='SETTLED'", "DELETE FROM commercial_collection_events"):
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            conn.execute(sql)
    conn.close()


def test_mark_reconciled_cannot_silently_change_its_reference(db):
    service = _service(db)
    c = _settle(service, _collection("c"))
    with pytest.raises(ValueError, match="already reconciled"):
        service.mark_reconciled(c, "a-different-recon")
    assert c.meta["reconciliation_reference"] == "recon-c"


# --- receipts ----------------------------------------------------------------

def test_paid_receipt_is_deterministic(db):
    c = _settle(_service(db), _collection("d"))
    assert generate_paid_receipt(c) == generate_paid_receipt(c)
    other = _settle(_service(db), _collection("e"))
    assert generate_paid_receipt(other).receipt_id != generate_paid_receipt(c).receipt_id


def test_adjustment_receipt_references_original_and_keeps_it_intact(db):
    service = _service(db)
    c = _settle(service, _collection("f"))
    paid = generate_paid_receipt(c)
    service.transition(c, CollectionStatus.CHARGEBACK)
    adj_txn = service.post_terminal_adjustment(c)

    at = _terminal_time(service, c)
    adjustment = generate_adjustment_receipt(c, original_receipt=paid, adjustment_ledger_txn_id=adj_txn.ledger_txn_id, adjusted_at=at)
    assert adjustment.status == "CHARGEBACK"
    assert adjustment.reversal_of_receipt_id == paid.receipt_id
    assert adjustment.receipt_id != paid.receipt_id
    assert adjustment.ledger_txn_id == adj_txn.ledger_txn_id
    assert adjustment.generated_at == at
    assert adjustment == generate_adjustment_receipt(c, original_receipt=paid, adjustment_ledger_txn_id=adj_txn.ledger_txn_id, adjusted_at=at)
    assert paid.status == "PAID"
    # The collection is no longer payable evidence, so a new PAID receipt is refused.
    with pytest.raises(ReceiptNotReconciledError):
        generate_paid_receipt(c)


def test_adjustment_receipt_fails_closed(db):
    service = _service(db)
    c = _settle(service, _collection("g"))
    paid = generate_paid_receipt(c)
    with pytest.raises(ReceiptNotReconciledError, match="terminal"):
        generate_adjustment_receipt(c, original_receipt=paid, adjustment_ledger_txn_id="adj-1", adjusted_at=datetime(2026, 9, 1))
    service.transition(c, CollectionStatus.REFUNDED)
    at = _terminal_time(service, c)
    with pytest.raises(ReceiptNotReconciledError, match="ledger"):
        generate_adjustment_receipt(c, original_receipt=paid, adjustment_ledger_txn_id="", adjusted_at=at)
    with pytest.raises(ReceiptNotReconciledError, match="recorded time"):
        generate_adjustment_receipt(c, original_receipt=paid, adjustment_ledger_txn_id="adj-1", adjusted_at=None)
    other = generate_paid_receipt(_settle(_service(db), _collection("h")))
    with pytest.raises(ReceiptNotReconciledError, match="original"):
        generate_adjustment_receipt(c, original_receipt=other, adjustment_ledger_txn_id="adj-1", adjusted_at=at)


# --- statements --------------------------------------------------------------

def _portfolio(db):
    service = _service(db)
    paid = _settle(service, _collection("p1", "100.00"))
    unreconciled = _settle(service, _collection("p2", "40.00"), reconcile=False)
    refunded = _settle(service, _collection("p3", "25.00"))
    service.transition(refunded, CollectionStatus.REFUNDED)
    service.post_terminal_adjustment(refunded)
    initiated = _collection("p4", "10.00")
    service.register(initiated)
    service.transition(initiated, CollectionStatus.INITIATED, provider_reference="prov-p4")
    failed = _collection("p5", "5.00")
    service.register(failed)
    service.transition(failed, CollectionStatus.FAILED)
    obligation = _collection("p6", "7.50")
    service.register(obligation)
    return service, [paid, unreconciled, refunded, initiated, failed, obligation]


def test_statement_classifies_every_state_and_never_overstates_paid(db):
    service, collections = _portfolio(db)
    statement = build_statement("cust-1", collections, history=service.history, open_exception_collection_ids={collections[1].collection_id})
    states = {line.obligation_id: line.state for line in statement.lines}
    assert states == {
        "obl-p1": "reconciled", "obl-p2": "settled", "obl-p3": "refunded",
        "obl-p4": "initiated", "obl-p5": "failed", "obl-p6": "obligation",
    }
    exceptions = {line.obligation_id for line in statement.lines if line.has_open_exception}
    assert exceptions == {"obl-p2"}
    usd = statement.totals["USD"]
    assert usd["paid"] == Decimal("100.00"), "only settled AND reconciled money is paid"
    assert usd["settled_unreconciled"] == Decimal("40.00")
    assert usd["reversed_refunded_chargeback"] == Decimal("25.00")
    assert usd["in_progress"] == Decimal("10.00")
    assert usd["failed"] == Decimal("5.00")
    assert usd["obligation"] == Decimal("7.50")
    assert usd["total_obligations"] == Decimal("187.50")
    refunded_line = [line for line in statement.lines if line.obligation_id == "obl-p3"][0]
    assert [e.to_status for e in refunded_line.events][-2:] == ["RECONCILED", "REFUNDED"]
    assert refunded_line.settlement_reference == "set-p3"


def test_statement_is_deterministic_and_reproducible_after_restart(db):
    service, collections = _portfolio(db)
    first = build_statement("cust-1", collections, history=service.history)
    reordered = build_statement("cust-1", list(reversed(collections)), history=CollectionHistoryRepository(db))
    assert first == reordered and first.statement_id == reordered.statement_id
    assert first.statement_id.startswith("CSS-STM-")


def test_statement_rejects_other_customers_records(db):
    service, collections = _portfolio(db)
    stranger = _collection("x", customer="cust-2")
    with pytest.raises(ValueError, match="cust-2"):
        build_statement("cust-1", collections + [stranger], history=service.history)
