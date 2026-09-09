from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
import json
import sqlite3

import pytest

import backend.app.persistence.repositories.base_repository as base_repository
import backend.app.persistence.migrations.runner as migration_runner
from backend.app.persistence.services.persistence_service import PersistenceService
from backend.app.persistence.repositories.platform_access_fee_terms_repository import (
    PlatformAccessFeeTermsRepository,
)
from backend.commercialization.platform_access_fee_terms import (
    CommercialPlatformAccessFeeTerms,
    PlatformAccessBillingFrequency,
)


START = "2026-09-09T00:00:00.123456Z"
END = "2027-01-01T00:00:00+00:00"


def terms(**changes):
    # Demonstration launch configuration, not a production singleton or date.
    values = dict(
        access_terms_id="ACCESS-INTRO-001",
        billing_currency="USD",
        access_fee_amount=Decimal("29.99"),
        billing_frequency=PlatformAccessBillingFrequency.MONTHLY,
        effective_from=START,
        evidence_refs=("agreement:access-intro", "approval:pricing"),
        accepted=True,
    )
    values.update(changes)
    return CommercialPlatformAccessFeeTerms(**values)


def test_initial_monthly_configuration():
    record = terms()
    assert record.billing_currency == "USD"
    assert record.access_fee_amount == Decimal("29.99")
    assert record.billing_frequency is PlatformAccessBillingFrequency.MONTHLY
    assert record.effective_from == START
    assert record.effective_to is None
    assert record.evidence_refs == ("agreement:access-intro", "approval:pricing")
    assert record.accepted is True


@pytest.mark.parametrize("amount", [Decimal("0"), Decimal("49.99"),
                                    Decimal("29.99000000000000000000000000001")])
def test_zero_future_and_exact_amounts(amount):
    assert terms(access_fee_amount=amount).access_fee_amount.as_tuple() == amount.as_tuple()


@pytest.mark.parametrize("amount", [29.99, 29, "29.99", None])
def test_non_decimal_rejected(amount):
    with pytest.raises(TypeError, match="Decimal"):
        terms(access_fee_amount=amount)


@pytest.mark.parametrize("amount", ["-0.01", "NaN", "sNaN", "Infinity", "-Infinity"])
def test_invalid_decimal_rejected(amount):
    with pytest.raises(ValueError):
        terms(access_fee_amount=Decimal(amount))


@pytest.mark.parametrize("identity", ["", " ", " ACCESS-A", "ACCESS-A "])
def test_invalid_identity(identity):
    with pytest.raises(ValueError, match="access_terms_id"):
        terms(access_terms_id=identity)


@pytest.mark.parametrize("currency", ["", " ", "usd", " USD", "USD ", "US", "USDD", "123", "CAD"])
def test_invalid_or_unsupported_currency(currency):
    with pytest.raises(ValueError, match="currency"):
        terms(billing_currency=currency)


def test_closed_effectivity():
    assert terms(effective_to=END).effective_to == END


@pytest.mark.parametrize("end", [START, "2026-09-09T00:00:00.123456+00:00",
                                 "2026-09-08T00:00:00Z"])
def test_end_must_be_strictly_later(end):
    with pytest.raises(ValueError, match="after"):
        terms(effective_to=end)


@pytest.mark.parametrize("field", ["effective_from", "effective_to"])
@pytest.mark.parametrize("timestamp", ["", "garbage", "2026-10-01T00:00:00",
                                      "2026-10-01T00:00:00+01:00", " 2026-10-01T00:00:00Z"])
def test_invalid_timestamps(field, timestamp):
    with pytest.raises(ValueError):
        terms(**{field: timestamp})


@pytest.mark.parametrize("accepted", [True, False])
def test_acceptance_records_state_without_authority(accepted):
    record = terms(accepted=accepted)
    assert record.accepted is accepted
    for name in ("real_fee_collection_allowed", "money_movement_allowed",
                 "invoice_creation_allowed", "receivable_recognition_allowed",
                 "tax_calculation_allowed", "ledger_posting_allowed", "execution_authority"):
        assert getattr(record, name) is False


@pytest.mark.parametrize("accepted", [0, 1, "true", None])
def test_acceptance_requires_bool(accepted):
    with pytest.raises(TypeError, match="accepted"):
        terms(accepted=accepted)


@pytest.mark.parametrize("refs", [(), ("",), (" padded",), (None,)])
def test_invalid_evidence(refs):
    with pytest.raises(ValueError, match="evidence"):
        terms(evidence_refs=refs)


def test_evidence_cannot_be_mutable():
    with pytest.raises(TypeError, match="tuple"):
        terms(evidence_refs=["agreement:A"])


@pytest.mark.parametrize("frequency", ["MONTHLY", "ANNUAL", None])
def test_frequency_requires_narrow_enum(frequency):
    with pytest.raises(TypeError, match="billing_frequency"):
        terms(billing_frequency=frequency)


def test_immutable_and_successor_is_separate():
    original = terms(effective_to=END)
    with pytest.raises(FrozenInstanceError):
        original.access_fee_amount = Decimal("49.99")
    successor = replace(original, access_terms_id="ACCESS-NEXT-002",
                        access_fee_amount=Decimal("49.99"),
                        effective_from=END, effective_to=None)
    assert original.access_fee_amount == Decimal("29.99")
    assert successor.access_fee_amount == Decimal("49.99")
    assert successor.access_terms_id != original.access_terms_id


@pytest.fixture
def service(monkeypatch, tmp_path):
    connection = sqlite3.connect(tmp_path / "access-terms.sqlite")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    monkeypatch.setattr(base_repository, "get_connection", lambda: connection)
    monkeypatch.setattr(migration_runner, "get_connection", lambda: connection)
    try:
        yield PersistenceService()
    finally:
        connection.close()


@pytest.mark.parametrize("accepted", [True, False])
@pytest.mark.parametrize("end", [None, END])
def test_persist_exact_round_trip(service, accepted, end):
    original = terms(access_fee_amount=Decimal("29.99000000000000000000000000001"),
                     accepted=accepted, effective_to=end)
    repo = service.platform_access_fee_terms
    with repo.transaction():
        repo.create_terms(original)
    row = repo.get_by_access_terms_id(original.access_terms_id)
    assert row["access_fee_amount"] == str(original.access_fee_amount)
    assert row["effective_from"] == START
    assert row["effective_to"] == end
    assert row["accepted"] == int(accepted)
    restored = CommercialPlatformAccessFeeTerms(
        access_terms_id=row["access_terms_id"],
        billing_currency=row["billing_currency"],
        access_fee_amount=Decimal(row["access_fee_amount"]),
        billing_frequency=PlatformAccessBillingFrequency(row["billing_frequency"]),
        effective_from=row["effective_from"], effective_to=row["effective_to"],
        evidence_refs=tuple(json.loads(row["evidence_refs_json"])),
        accepted=bool(row["accepted"]),
    )
    assert restored == original
    assert restored.access_fee_amount.as_tuple() == original.access_fee_amount.as_tuple()


def test_duplicate_does_not_overwrite_history(service):
    repo = service.platform_access_fee_terms
    original = terms(effective_to=END)
    repo.create_terms(original)
    before = repo.get_by_access_terms_id(original.access_terms_id)
    with pytest.raises(sqlite3.IntegrityError):
        repo.create_terms(replace(original, access_fee_amount=Decimal("49.99")))
    assert repo.get_by_access_terms_id(original.access_terms_id) == before
    successor = terms(access_terms_id="ACCESS-NEXT-002", effective_from=END,
                      access_fee_amount=Decimal("49.99"))
    repo.create_terms(successor)
    assert len(repo.list_all()) == 2
    assert repo.get_by_access_terms_id(original.access_terms_id) == before
    assert not hasattr(repo, "update_terms")
    assert not hasattr(repo, "delete_terms")


def test_service_migration_and_reinitialization(service):
    repo = service.platform_access_fee_terms
    assert isinstance(repo, PlatformAccessFeeTermsRepository)
    assert service.healthcheck()["repositories"]["platform_access_fee_terms"] is True
    repo.create_terms(terms())
    again = PersistenceService()
    assert len(again.platform_access_fee_terms.list_all()) == 1
    assert repo.fetch_one(
        "SELECT count(*) AS n FROM schema_migrations WHERE version = ?",
        ("024_platform_access_fee_terms",),
    )["n"] == 1
    assert repo.get_by_access_terms_id("missing") is None


def test_repository_rejects_wrong_record_type(service):
    with pytest.raises(TypeError, match="CommercialPlatformAccessFeeTerms"):
        service.platform_access_fee_terms.create_terms(object())
