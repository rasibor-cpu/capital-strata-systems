from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

import backend.app.persistence.repositories.base_repository as base_repository
from backend.app.persistence.repositories.billing_profile_repository import (
    BillingProfileRepository,
)
from backend.commercialization.billing_profile import (
    BillingPartyType,
    CommercialBillingProfile,
    PaymentTermsStatus,
    TaxTreatmentStatus,
    build_commercial_billing_profile,
)


MIGRATION_012 = Path(
    "backend/app/persistence/migrations/sql/"
    "012_billing_profile.sql"
)

EFFECTIVE_FROM = "2026-01-01T00:00:00+00:00"
EFFECTIVE_TO = "2026-12-31T00:00:00+00:00"


@pytest.fixture
def db(monkeypatch):
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    connection.executescript(
        """
        CREATE TABLE performance_compensation_terms (
            terms_id TEXT PRIMARY KEY
        );
        """
    )
    connection.executescript(
        MIGRATION_012.read_text(encoding="utf-8-sig")
    )

    monkeypatch.setattr(
        base_repository,
        "get_connection",
        lambda: connection,
    )

    yield connection

    connection.close()


def _create_terms(
    connection: sqlite3.Connection,
    terms_id: str = "TERMS-001",
) -> None:
    connection.execute(
        """
        INSERT INTO performance_compensation_terms (terms_id)
        VALUES (?)
        """,
        (terms_id,),
    )


def _profile(
    *,
    billing_profile_id: str = "BP-001",
    terms_id: str = "TERMS-001",
    party_type: BillingPartyType = BillingPartyType.ORGANIZATION,
    bill_to_name: str = "Acme Capital Ltd",
    bill_to_reference: str = "BILLTO-ACME-1",
    seller_reference: str = "SELLER-CSS-1",
    tax_treatment_status: TaxTreatmentStatus = (
        TaxTreatmentStatus.OUT_OF_SCOPE
    ),
    payment_terms_status: PaymentTermsStatus = (
        PaymentTermsStatus.DEFINED_EXTERNALLY
    ),
    effective_from: str = EFFECTIVE_FROM,
    evidence_refs: tuple[str, ...] = ("profile:BP-001",),
    effective_to: str | None = None,
) -> CommercialBillingProfile:
    return build_commercial_billing_profile(
        billing_profile_id=billing_profile_id,
        terms_id=terms_id,
        party_type=party_type,
        bill_to_name=bill_to_name,
        bill_to_reference=bill_to_reference,
        seller_reference=seller_reference,
        tax_treatment_status=tax_treatment_status,
        payment_terms_status=payment_terms_status,
        effective_from=effective_from,
        evidence_refs=evidence_refs,
        effective_to=effective_to,
    )


def _profile_from_row(row: dict) -> CommercialBillingProfile:
    return CommercialBillingProfile(
        billing_profile_id=row["billing_profile_id"],
        terms_id=row["terms_id"],
        party_type=BillingPartyType(row["party_type"]),
        bill_to_name=row["bill_to_name"],
        bill_to_reference=row["bill_to_reference"],
        seller_reference=row["seller_reference"],
        tax_treatment_status=TaxTreatmentStatus(
            row["tax_treatment_status"]
        ),
        payment_terms_status=PaymentTermsStatus(
            row["payment_terms_status"]
        ),
        effective_from=row["effective_from"],
        evidence_refs=tuple(json.loads(row["evidence_refs_json"])),
        effective_to=row["effective_to"],
    )


def test_insert_and_read_individual_profile(db):
    _create_terms(db)
    profile = _profile(
        party_type=BillingPartyType.INDIVIDUAL,
        bill_to_name="Jane Doe",
        bill_to_reference="BILLTO-JD-1",
    )
    BillingProfileRepository().create_profile(profile)

    row = BillingProfileRepository().get_by_profile_id("BP-001")

    assert row is not None
    assert row["party_type"] == "INDIVIDUAL"
    assert row["bill_to_name"] == "Jane Doe"
    assert row["terms_id"] == "TERMS-001"


def test_insert_and_read_organization_profile(db):
    _create_terms(db)
    BillingProfileRepository().create_profile(_profile())

    row = BillingProfileRepository().get_by_profile_id("BP-001")

    assert row is not None
    assert row["party_type"] == "ORGANIZATION"
    assert row["seller_reference"] == "SELLER-CSS-1"


def test_party_type_exact_serialization(db):
    _create_terms(db)
    BillingProfileRepository().create_profile(
        _profile(party_type=BillingPartyType.INDIVIDUAL)
    )

    row = BillingProfileRepository().get_by_profile_id("BP-001")

    assert row is not None
    assert row["party_type"] == "INDIVIDUAL"
    assert BillingPartyType(row["party_type"]) is (
        BillingPartyType.INDIVIDUAL
    )


def test_tax_status_exact_serialization(db):
    _create_terms(db)
    BillingProfileRepository().create_profile(
        _profile(tax_treatment_status=TaxTreatmentStatus.EXEMPT)
    )

    row = BillingProfileRepository().get_by_profile_id("BP-001")

    assert row is not None
    assert row["tax_treatment_status"] == "EXEMPT"
    assert TaxTreatmentStatus(row["tax_treatment_status"]) is (
        TaxTreatmentStatus.EXEMPT
    )


def test_payment_terms_status_exact_serialization(db):
    _create_terms(db)
    BillingProfileRepository().create_profile(
        _profile(
            payment_terms_status=PaymentTermsStatus.NOT_REQUIRED
        )
    )

    row = BillingProfileRepository().get_by_profile_id("BP-001")

    assert row is not None
    assert row["payment_terms_status"] == "NOT_REQUIRED"
    assert PaymentTermsStatus(row["payment_terms_status"]) is (
        PaymentTermsStatus.NOT_REQUIRED
    )


def test_evidence_json_round_trip(db):
    _create_terms(db)
    BillingProfileRepository().create_profile(
        _profile(
            evidence_refs=(
                "profile:BP-001",
                "acceptance:USER-1",
            )
        )
    )

    row = BillingProfileRepository().get_by_profile_id("BP-001")

    assert row is not None
    assert row["evidence_refs_json"] == (
        '["profile:BP-001","acceptance:USER-1"]'
    )
    assert json.loads(row["evidence_refs_json"]) == [
        "profile:BP-001",
        "acceptance:USER-1",
    ]


def test_effective_to_null_round_trip(db):
    _create_terms(db)
    BillingProfileRepository().create_profile(
        _profile(effective_to=None)
    )

    row = BillingProfileRepository().get_by_profile_id("BP-001")

    assert row is not None
    assert row["effective_to"] is None
    assert _profile_from_row(row).effective_to is None


def test_populated_effective_to_round_trip(db):
    _create_terms(db)
    BillingProfileRepository().create_profile(
        _profile(effective_to=EFFECTIVE_TO)
    )

    row = BillingProfileRepository().get_by_profile_id("BP-001")

    assert row is not None
    assert row["effective_to"] == EFFECTIVE_TO
    assert _profile_from_row(row).effective_to == EFFECTIVE_TO


def test_duplicate_billing_profile_id_rejected(db):
    _create_terms(db)
    repo = BillingProfileRepository()
    repo.create_profile(_profile())

    with pytest.raises(sqlite3.IntegrityError):
        repo.create_profile(
            _profile(
                bill_to_name="Other Name",
            )
        )


def test_missing_terms_fk_rejected(db):
    with pytest.raises(sqlite3.IntegrityError):
        BillingProfileRepository().create_profile(
            _profile(terms_id="MISSING-TERMS")
        )


def test_blank_billing_profile_id_rejected_at_db_layer(db):
    _create_terms(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_billing_profiles (
                billing_profile_id,
                terms_id,
                party_type,
                bill_to_name,
                bill_to_reference,
                seller_reference,
                tax_treatment_status,
                payment_terms_status,
                effective_from,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                " ",
                "TERMS-001",
                "ORGANIZATION",
                "Acme Capital Ltd",
                "BILLTO-ACME-1",
                "SELLER-CSS-1",
                "OUT_OF_SCOPE",
                "DEFINED_EXTERNALLY",
                EFFECTIVE_FROM,
                '["profile:BP-BLANK"]',
            ),
        )


def test_invalid_party_type_rejected_at_db_layer(db):
    _create_terms(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_billing_profiles (
                billing_profile_id,
                terms_id,
                party_type,
                bill_to_name,
                bill_to_reference,
                seller_reference,
                tax_treatment_status,
                payment_terms_status,
                effective_from,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "BP-BAD-PARTY",
                "TERMS-001",
                "CORPORATION",
                "Acme Capital Ltd",
                "BILLTO-ACME-1",
                "SELLER-CSS-1",
                "OUT_OF_SCOPE",
                "DEFINED_EXTERNALLY",
                EFFECTIVE_FROM,
                '["profile:BP-BAD-PARTY"]',
            ),
        )


def test_invalid_tax_status_rejected_at_db_layer(db):
    _create_terms(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_billing_profiles (
                billing_profile_id,
                terms_id,
                party_type,
                bill_to_name,
                bill_to_reference,
                seller_reference,
                tax_treatment_status,
                payment_terms_status,
                effective_from,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "BP-BAD-TAX",
                "TERMS-001",
                "ORGANIZATION",
                "Acme Capital Ltd",
                "BILLTO-ACME-1",
                "SELLER-CSS-1",
                "TAXABLE",
                "DEFINED_EXTERNALLY",
                EFFECTIVE_FROM,
                '["profile:BP-BAD-TAX"]',
            ),
        )


def test_invalid_payment_terms_status_rejected_at_db_layer(db):
    _create_terms(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_billing_profiles (
                billing_profile_id,
                terms_id,
                party_type,
                bill_to_name,
                bill_to_reference,
                seller_reference,
                tax_treatment_status,
                payment_terms_status,
                effective_from,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "BP-BAD-TERMS",
                "TERMS-001",
                "ORGANIZATION",
                "Acme Capital Ltd",
                "BILLTO-ACME-1",
                "SELLER-CSS-1",
                "OUT_OF_SCOPE",
                "NET_30",
                EFFECTIVE_FROM,
                '["profile:BP-BAD-TERMS"]',
            ),
        )


def test_blank_bill_to_name_rejected(db):
    _create_terms(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_billing_profiles (
                billing_profile_id,
                terms_id,
                party_type,
                bill_to_name,
                bill_to_reference,
                seller_reference,
                tax_treatment_status,
                payment_terms_status,
                effective_from,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "BP-BLANK-NAME",
                "TERMS-001",
                "ORGANIZATION",
                " ",
                "BILLTO-ACME-1",
                "SELLER-CSS-1",
                "OUT_OF_SCOPE",
                "DEFINED_EXTERNALLY",
                EFFECTIVE_FROM,
                '["profile:BP-BLANK-NAME"]',
            ),
        )


def test_blank_bill_to_reference_rejected(db):
    _create_terms(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_billing_profiles (
                billing_profile_id,
                terms_id,
                party_type,
                bill_to_name,
                bill_to_reference,
                seller_reference,
                tax_treatment_status,
                payment_terms_status,
                effective_from,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "BP-BLANK-REF",
                "TERMS-001",
                "ORGANIZATION",
                "Acme Capital Ltd",
                "",
                "SELLER-CSS-1",
                "OUT_OF_SCOPE",
                "DEFINED_EXTERNALLY",
                EFFECTIVE_FROM,
                '["profile:BP-BLANK-REF"]',
            ),
        )


def test_blank_seller_reference_rejected(db):
    _create_terms(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_billing_profiles (
                billing_profile_id,
                terms_id,
                party_type,
                bill_to_name,
                bill_to_reference,
                seller_reference,
                tax_treatment_status,
                payment_terms_status,
                effective_from,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "BP-BLANK-SELLER",
                "TERMS-001",
                "ORGANIZATION",
                "Acme Capital Ltd",
                "BILLTO-ACME-1",
                " ",
                "OUT_OF_SCOPE",
                "DEFINED_EXTERNALLY",
                EFFECTIVE_FROM,
                '["profile:BP-BLANK-SELLER"]',
            ),
        )


def test_empty_evidence_rejected(db):
    _create_terms(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_billing_profiles (
                billing_profile_id,
                terms_id,
                party_type,
                bill_to_name,
                bill_to_reference,
                seller_reference,
                tax_treatment_status,
                payment_terms_status,
                effective_from,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "BP-EMPTY-EV",
                "TERMS-001",
                "ORGANIZATION",
                "Acme Capital Ltd",
                "BILLTO-ACME-1",
                "SELLER-CSS-1",
                "OUT_OF_SCOPE",
                "DEFINED_EXTERNALLY",
                EFFECTIVE_FROM,
                "[]",
            ),
        )


def test_get_by_profile_id_is_deterministic(db):
    _create_terms(db)
    BillingProfileRepository().create_profile(_profile())

    first = BillingProfileRepository().get_by_profile_id("BP-001")
    second = BillingProfileRepository().get_by_profile_id("BP-001")

    assert first is not None
    assert second is not None
    assert first == second


def test_lookup_and_list_are_deterministic(db):
    _create_terms(db, "TERMS-001")
    _create_terms(db, "TERMS-002")

    repo = BillingProfileRepository()
    repo.create_profile(
        _profile(
            billing_profile_id="BP-B",
            terms_id="TERMS-001",
        )
    )
    repo.create_profile(
        _profile(
            billing_profile_id="BP-A",
            terms_id="TERMS-001",
            bill_to_name="Other Org",
            bill_to_reference="BILLTO-OTHER-1",
        )
    )
    repo.create_profile(
        _profile(
            billing_profile_id="BP-C",
            terms_id="TERMS-002",
        )
    )

    by_terms = repo.get_by_terms_id("TERMS-001")
    listed = repo.list_all()

    # Ordering: created_at ASC, billing_profile_id ASC.
    assert [row["billing_profile_id"] for row in by_terms] == [
        "BP-A",
        "BP-B",
    ]
    assert [row["billing_profile_id"] for row in listed] == [
        "BP-A",
        "BP-B",
        "BP-C",
    ]


def test_repository_has_no_mutation_api():
    assert not hasattr(BillingProfileRepository, "update_profile")
    assert not hasattr(BillingProfileRepository, "delete_profile")
    assert not hasattr(BillingProfileRepository, "update")
    assert not hasattr(BillingProfileRepository, "delete")


def test_ready_profile_readiness_round_trip(db):
    _create_terms(db)
    BillingProfileRepository().create_profile(
        _profile(
            tax_treatment_status=TaxTreatmentStatus.OUT_OF_SCOPE,
            payment_terms_status=PaymentTermsStatus.DEFINED_EXTERNALLY,
        )
    )

    row = BillingProfileRepository().get_by_profile_id("BP-001")
    assert row is not None
    persisted = _profile_from_row(row)

    assert persisted.invoice_identity_ready is True
    assert persisted.tax_ready is True
    assert persisted.payment_terms_ready is True
    assert persisted.invoice_candidate_ready is True


def test_unresolved_tax_readiness_round_trip(db):
    _create_terms(db)
    BillingProfileRepository().create_profile(
        _profile(
            tax_treatment_status=TaxTreatmentStatus.UNDETERMINED,
            payment_terms_status=PaymentTermsStatus.DEFINED_EXTERNALLY,
        )
    )

    row = BillingProfileRepository().get_by_profile_id("BP-001")
    assert row is not None
    persisted = _profile_from_row(row)

    assert persisted.tax_ready is False
    assert persisted.invoice_candidate_ready is False


def test_unresolved_payment_terms_readiness_round_trip(db):
    _create_terms(db)
    BillingProfileRepository().create_profile(
        _profile(
            tax_treatment_status=TaxTreatmentStatus.EXEMPT,
            payment_terms_status=PaymentTermsStatus.REQUIRES_DEFINITION,
        )
    )

    row = BillingProfileRepository().get_by_profile_id("BP-001")
    assert row is not None
    persisted = _profile_from_row(row)

    assert persisted.payment_terms_ready is False
    assert persisted.invoice_candidate_ready is False


def test_persisted_profile_has_no_invoice_ar_or_payment_authority(db):
    _create_terms(db)
    BillingProfileRepository().create_profile(
        _profile(
            tax_treatment_status=TaxTreatmentStatus.OUT_OF_SCOPE,
            payment_terms_status=PaymentTermsStatus.DEFINED_EXTERNALLY,
        )
    )

    row = BillingProfileRepository().get_by_profile_id("BP-001")
    assert row is not None
    persisted = _profile_from_row(row)

    assert persisted.invoice_candidate_ready is True
    assert persisted.invoice_creation_allowed is False
    assert persisted.receivable_recognition_allowed is False
    assert persisted.ledger_posting_allowed is False
    assert persisted.revenue_recognition_allowed is False
    assert persisted.tax_calculation_allowed is False
    assert persisted.due_balance_creation_allowed is False
    assert persisted.real_fee_collection_allowed is False
    assert persisted.client_funds_deduction_allowed is False
    assert persisted.automatic_debit_allowed is False
    assert persisted.invoice_settlement_allowed is False
    assert persisted.payment_initiation_allowed is False
    assert persisted.money_movement_allowed is False
    assert persisted.broker_withdrawal_allowed is False
    assert persisted.execution_authority is False
