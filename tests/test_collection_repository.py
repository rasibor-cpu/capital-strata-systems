from decimal import Decimal

from engine.commercial.collection_repository import CollectionRepository
from engine.domain.collections import CollectionStatus, CollectionTransaction


def make_collection():
    return CollectionTransaction(
        obligation_id="obl-persist-1",
        customer_id="cust-1",
        account_id="acct-1",
        amount=Decimal("25.00"),
        currency="CAD",
        idempotency_key="persist-key-1",
    )


def test_collection_round_trip_survives_repository_reopen(tmp_path):
    db = tmp_path / "commercial.sqlite3"
    repo = CollectionRepository(str(db))
    c = make_collection()
    c.status = CollectionStatus.SETTLED
    c.provider_reference = "provider-1"
    c.settlement_reference = "settle-1"
    c.ledger_txn_id = "ledger-1"
    c.meta["reconciliation_reference"] = "recon-1"
    repo.save(c)

    restored = CollectionRepository(str(db)).get_by_idempotency_key(c.idempotency_key)
    assert restored is not None
    assert restored.collection_id == c.collection_id
    assert restored.status == CollectionStatus.SETTLED
    assert restored.amount == Decimal("25.00")
    assert restored.settlement_reference == "settle-1"
    assert restored.meta["reconciliation_reference"] == "recon-1"


def test_idempotency_key_is_unique_across_restart(tmp_path):
    db = tmp_path / "commercial.sqlite3"
    repo = CollectionRepository(str(db))
    first = make_collection()
    repo.save(first)

    second = make_collection()
    second.collection_id = "different-collection"
    try:
        repo.save(second)
        raised = False
    except Exception:
        raised = True
    assert raised
    restored = CollectionRepository(str(db)).get_by_idempotency_key("persist-key-1")
    assert restored.collection_id == first.collection_id
