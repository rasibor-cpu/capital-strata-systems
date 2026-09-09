from __future__ import annotations

import json
import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest

import backend.app.persistence.repositories.base_repository as base_repository
from backend.app.persistence.repositories.billable_obligation_repository import (
    BillableObligationRepository,
)
from backend.app.persistence.repositories.billing_profile_repository import (
    BillingProfileRepository,
)
from backend.app.persistence.repositories.crystallization_assessment_repository import (
    CrystallizationAssessmentRepository,
)
from backend.app.persistence.repositories.invoice_candidate_repository import (
    InvoiceCandidateRepository,
)
from backend.app.persistence.repositories.invoice_identity_repository import (
    InvoiceIdentityRepository,
)
from backend.app.persistence.repositories.invoice_issued_repository import (
    InvoiceIssuedRepository,
)
from backend.app.persistence.repositories.performance_compensation_lifecycle_policy_repository import (
    PerformanceCompensationLifecyclePolicyRepository,
)
from backend.app.persistence.repositories.settlement_readiness_repository import (
    SettlementReadinessRepository,
)
from backend.commercialization.billable_obligation import (
    BillableObligationStatus,
    build_billable_obligation,
)
from backend.commercialization.billing_profile import (
    BillingPartyType,
    PaymentTermsStatus,
    TaxTreatmentStatus,
    build_commercial_billing_profile,
)
from backend.commercialization.invoice_candidate import (
    InvoiceCandidateStatus,
    build_invoice_candidate,
)
from backend.commercialization.invoice_identity import (
    CommercialInvoiceIdentityAllocation,
    build_invoice_identity_allocation,
)
from backend.commercialization.invoice_issued import (
    CommercialInvoiceIssuedRecord,
    build_invoice_issued_record,
)
from backend.commercialization.performance_crystallization import (
    CrystallizationAssessment,
    CrystallizationFrequency,
    CrystallizationStatus,
    PerformanceCompensationLifecyclePolicy,
)
from backend.commercialization.settlement_readiness import (
    SettlementReadinessStatus,
    build_settlement_readiness,
)


MIGRATION_009 = Path(
    "backend/app/persistence/migrations/sql/"
    "009_performance_crystallization.sql"
)
MIGRATION_010 = Path(
    "backend/app/persistence/migrations/sql/"
    "010_settlement_readiness.sql"
)
MIGRATION_011 = Path(
    "backend/app/persistence/migrations/sql/"
    "011_billable_obligation.sql"
)
MIGRATION_012 = Path(
    "backend/app/persistence/migrations/sql/"
    "012_billing_profile.sql"
)
MIGRATION_013 = Path(
    "backend/app/persistence/migrations/sql/"
    "013_invoice_candidate.sql"
)
MIGRATION_014 = Path(
    "backend/app/persistence/migrations/sql/"
    "014_invoice_identity.sql"
)
MIGRATION_015 = Path(
    "backend/app/persistence/migrations/sql/"
    "015_invoice_issued.sql"
)

UTC_FROM = "2026-01-01T00:00:00+00:00"
UTC_TO = "2026-12-31T00:00:00+00:00"
PERIOD_START = "2026-03-01T00:00:00+00:00"
PERIOD_END = "2026-04-01T00:00:00+00:00"
PERIOD_START_2 = "2026-05-01T00:00:00+00:00"
PERIOD_END_2 = "2026-06-01T00:00:00+00:00"
ASSESSED_AT = "2026-04-01T12:00:00+00:00"
READINESS_AT = "2026-04-02T09:00:00+00:00"
RECOGNIZED_AT = "2026-04-03T10:00:00+00:00"
CANDIDATE_AT = "2026-04-04T11:00:00+00:00"
ALLOCATED_AT = "2026-04-05T12:00:00+00:00"
ISSUED_AT = "2026-04-06T13:00:00+00:00"


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
    for migration in (
        MIGRATION_009,
        MIGRATION_010,
        MIGRATION_011,
        MIGRATION_012,
        MIGRATION_013,
        MIGRATION_014,
        MIGRATION_015,
    ):
        connection.executescript(
            migration.read_text(encoding="utf-8-sig")
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


def _policy(
    *,
    policy_id: str = "POLICY-001",
    terms_id: str = "TERMS-001",
) -> PerformanceCompensationLifecyclePolicy:
    return PerformanceCompensationLifecyclePolicy(
        policy_id=policy_id,
        terms_id=terms_id,
        currency="CAD",
        crystallization_frequency=CrystallizationFrequency.QUARTERLY,
        effective_from=UTC_FROM,
        evidence_refs=("policy:POLICY-001",),
        crystallize_on_termination=False,
        effective_to=UTC_TO,
    )


def _assessment(
    *,
    policy: PerformanceCompensationLifecyclePolicy | None = None,
    crystallizable: Decimal = Decimal("1"),
    period_start: str = PERIOD_START,
    period_end: str = PERIOD_END,
) -> CrystallizationAssessment:
    policy = policy or _policy()
    return CrystallizationAssessment(
        policy_id=policy.policy_id,
        terms_id=policy.terms_id,
        currency=policy.currency,
        period_start=period_start,
        period_end=period_end,
        assessed_at=ASSESSED_AT,
        shadow_entitlement_total=crystallizable,
        crystallizable_amount=crystallizable,
        status=CrystallizationStatus.ELIGIBLE,
        evidence_refs=("assessment:Q1",),
    )


def _seed_allocation(
    connection: sqlite3.Connection,
    *,
    crystallizable: Decimal = Decimal("1"),
    period_start: str = PERIOD_START,
    period_end: str = PERIOD_END,
    billing_profile_id: str = "BP-001",
    invoice_id: str = "INV-ID-001",
    invoice_number: str | None = None,
    create_allocation: bool = True,
) -> CommercialInvoiceIdentityAllocation | None:
    policy = _policy()
    assessment = _assessment(
        policy=policy,
        crystallizable=crystallizable,
        period_start=period_start,
        period_end=period_end,
    )

    existing = connection.execute(
        """
        SELECT 1
        FROM performance_compensation_terms
        WHERE terms_id = ?
        """,
        (policy.terms_id,),
    ).fetchone()
    if existing is None:
        _create_terms(connection, policy.terms_id)

    existing_policy = connection.execute(
        """
        SELECT 1
        FROM performance_compensation_lifecycle_policies
        WHERE policy_id = ?
        """,
        (policy.policy_id,),
    ).fetchone()
    if existing_policy is None:
        PerformanceCompensationLifecyclePolicyRepository().create_policy(
            policy
        )

    CrystallizationAssessmentRepository().create_assessment(assessment)
    readiness = build_settlement_readiness(
        assessment,
        SettlementReadinessStatus.READY,
        READINESS_AT,
        ("readiness:OPS-1",),
    )
    SettlementReadinessRepository().create_readiness(readiness)

    obligation = build_billable_obligation(
        readiness,
        BillableObligationStatus.BILLABLE,
        RECOGNIZED_AT,
        ("billable:OPS-1",),
    )
    BillableObligationRepository().create_obligation(obligation)

    existing_profile = connection.execute(
        """
        SELECT 1
        FROM commercial_billing_profiles
        WHERE billing_profile_id = ?
        """,
        (billing_profile_id,),
    ).fetchone()
    if existing_profile is None:
        profile = build_commercial_billing_profile(
            billing_profile_id=billing_profile_id,
            terms_id=policy.terms_id,
            party_type=BillingPartyType.ORGANIZATION,
            bill_to_name="Acme Capital Ltd",
            bill_to_reference="BILLTO-ACME-1",
            seller_reference="SELLER-CSS-1",
            tax_treatment_status=TaxTreatmentStatus.OUT_OF_SCOPE,
            payment_terms_status=PaymentTermsStatus.DEFINED_EXTERNALLY,
            effective_from=UTC_FROM,
            evidence_refs=("profile:BP-001",),
            effective_to=UTC_TO,
        )
        BillingProfileRepository().create_profile(profile)
    else:
        profile = build_commercial_billing_profile(
            billing_profile_id=billing_profile_id,
            terms_id=policy.terms_id,
            party_type=BillingPartyType.ORGANIZATION,
            bill_to_name="Acme Capital Ltd",
            bill_to_reference="BILLTO-ACME-1",
            seller_reference="SELLER-CSS-1",
            tax_treatment_status=TaxTreatmentStatus.OUT_OF_SCOPE,
            payment_terms_status=PaymentTermsStatus.DEFINED_EXTERNALLY,
            effective_from=UTC_FROM,
            evidence_refs=("profile:BP-001",),
            effective_to=UTC_TO,
        )

    candidate = build_invoice_candidate(
        obligation,
        profile,
        InvoiceCandidateStatus.READY,
        CANDIDATE_AT,
        ("candidate:OPS-1",),
    )
    InvoiceCandidateRepository().create_candidate(candidate)

    if not create_allocation:
        return None

    allocation = build_invoice_identity_allocation(
        candidate,
        invoice_id=invoice_id,
        allocated_at=ALLOCATED_AT,
        evidence_refs=("identity:OPS-1",),
        invoice_number=invoice_number,
    )
    InvoiceIdentityRepository().create_allocation(allocation)
    return allocation


def _issued(
    allocation: CommercialInvoiceIdentityAllocation,
    *,
    evidence_refs: tuple[str, ...] = ("issued:OPS-1",),
) -> CommercialInvoiceIssuedRecord:
    return build_invoice_issued_record(
        allocation,
        issued_at=ISSUED_AT,
        evidence_refs=evidence_refs,
    )


def test_issued_record_with_invoice_number_none_round_trip(db):
    allocation = _seed_allocation(db, invoice_number=None)
    InvoiceIssuedRepository().create_issued_record(_issued(allocation))

    row = InvoiceIssuedRepository().get_by_invoice_id("INV-ID-001")

    assert row is not None
    assert row["invoice_id"] == "INV-ID-001"
    assert row["invoice_number"] is None
    assert row["invoice_amount"] == "1"
    assert row["issued_at"] == ISSUED_AT


def test_issued_record_with_invoice_number_present_round_trip(db):
    allocation = _seed_allocation(
        db,
        invoice_number="INV-2026-0001",
    )
    InvoiceIssuedRepository().create_issued_record(_issued(allocation))

    row = InvoiceIssuedRepository().get_by_invoice_number(
        "INV-2026-0001"
    )

    assert row is not None
    assert row["invoice_number"] == "INV-2026-0001"
    assert row["invoice_id"] == "INV-ID-001"


def test_exact_decimal_serialization(db):
    allocation = _seed_allocation(
        db,
        crystallizable=Decimal("3.50"),
    )
    InvoiceIssuedRepository().create_issued_record(_issued(allocation))

    row = InvoiceIssuedRepository().get_by_invoice_id("INV-ID-001")

    assert row is not None
    assert row["invoice_amount"] == "3.50"
    assert Decimal(row["invoice_amount"]) == Decimal("3.50")


def test_evidence_round_trip(db):
    allocation = _seed_allocation(db)
    InvoiceIssuedRepository().create_issued_record(
        _issued(
            allocation,
            evidence_refs=("issued:OPS-1", "review:OPS-2"),
        )
    )

    row = InvoiceIssuedRepository().get_by_invoice_id("INV-ID-001")

    assert row is not None
    assert row["evidence_refs_json"] == (
        '["issued:OPS-1","review:OPS-2"]'
    )
    assert tuple(json.loads(row["evidence_refs_json"])) == (
        "issued:OPS-1",
        "review:OPS-2",
    )


def test_duplicate_invoice_id_rejected(db):
    allocation = _seed_allocation(db)
    repo = InvoiceIssuedRepository()
    repo.create_issued_record(_issued(allocation))

    with pytest.raises(sqlite3.IntegrityError):
        repo.create_issued_record(_issued(allocation))


def test_missing_invoice_identity_fk_rejected(db):
    _seed_allocation(db, create_allocation=False)

    record = CommercialInvoiceIssuedRecord(
        invoice_id="INV-MISSING",
        policy_id="POLICY-001",
        terms_id="TERMS-001",
        billing_profile_id="BP-001",
        currency="CAD",
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        invoice_amount=Decimal("1"),
        invoice_number=None,
        issued_at=ISSUED_AT,
        evidence_refs=("issued:OPS-1",),
    )

    with pytest.raises(sqlite3.IntegrityError):
        InvoiceIssuedRepository().create_issued_record(record)


def test_missing_billing_profile_fk_rejected(db):
    allocation = _seed_allocation(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_invoice_issued_records (
                invoice_id,
                policy_id,
                terms_id,
                billing_profile_id,
                currency,
                period_start,
                period_end,
                invoice_amount,
                invoice_number,
                issued_at,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                allocation.invoice_id,
                allocation.policy_id,
                allocation.terms_id,
                "BP-MISSING",
                allocation.currency,
                allocation.period_start,
                allocation.period_end,
                str(allocation.invoice_amount),
                None,
                ISSUED_AT,
                '["issued:OPS-1"]',
            ),
        )


def test_missing_terms_fk_rejected(db):
    allocation = _seed_allocation(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_invoice_issued_records (
                invoice_id,
                policy_id,
                terms_id,
                billing_profile_id,
                currency,
                period_start,
                period_end,
                invoice_amount,
                invoice_number,
                issued_at,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                allocation.invoice_id,
                allocation.policy_id,
                "MISSING-TERMS",
                allocation.billing_profile_id,
                allocation.currency,
                allocation.period_start,
                allocation.period_end,
                str(allocation.invoice_amount),
                None,
                ISSUED_AT,
                '["issued:OPS-1"]',
            ),
        )


def test_lowercase_currency_rejected(db):
    allocation = _seed_allocation(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_invoice_issued_records (
                invoice_id,
                policy_id,
                terms_id,
                billing_profile_id,
                currency,
                period_start,
                period_end,
                invoice_amount,
                invoice_number,
                issued_at,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                allocation.invoice_id,
                allocation.policy_id,
                allocation.terms_id,
                allocation.billing_profile_id,
                "cad",
                allocation.period_start,
                allocation.period_end,
                str(allocation.invoice_amount),
                None,
                ISSUED_AT,
                '["issued:OPS-1"]',
            ),
        )


def test_blank_non_null_invoice_number_rejected(db):
    allocation = _seed_allocation(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_invoice_issued_records (
                invoice_id,
                policy_id,
                terms_id,
                billing_profile_id,
                currency,
                period_start,
                period_end,
                invoice_amount,
                invoice_number,
                issued_at,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                allocation.invoice_id,
                allocation.policy_id,
                allocation.terms_id,
                allocation.billing_profile_id,
                allocation.currency,
                allocation.period_start,
                allocation.period_end,
                str(allocation.invoice_amount),
                " ",
                ISSUED_AT,
                '["issued:OPS-1"]',
            ),
        )


def test_empty_evidence_rejected(db):
    allocation = _seed_allocation(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_invoice_issued_records (
                invoice_id,
                policy_id,
                terms_id,
                billing_profile_id,
                currency,
                period_start,
                period_end,
                invoice_amount,
                invoice_number,
                issued_at,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                allocation.invoice_id,
                allocation.policy_id,
                allocation.terms_id,
                allocation.billing_profile_id,
                allocation.currency,
                allocation.period_start,
                allocation.period_end,
                str(allocation.invoice_amount),
                None,
                ISSUED_AT,
                "[]",
            ),
        )


def test_deterministic_reads(db):
    allocation = _seed_allocation(
        db,
        invoice_id="INV-ID-001",
    )
    allocation2 = _seed_allocation(
        db,
        period_start=PERIOD_START_2,
        period_end=PERIOD_END_2,
        crystallizable=Decimal("2"),
        invoice_id="INV-ID-002",
    )
    repo = InvoiceIssuedRepository()
    repo.create_issued_record(_issued(allocation2))
    repo.create_issued_record(_issued(allocation))

    by_terms = repo.get_by_terms_id("TERMS-001")
    by_profile = repo.get_by_billing_profile_id("BP-001")
    listed = repo.list_all()

    expected = [PERIOD_START, PERIOD_START_2]
    assert [row["period_start"] for row in by_terms] == expected
    assert [row["period_start"] for row in by_profile] == expected
    assert [row["period_start"] for row in listed] == expected


def test_no_update_delete_api():
    assert not hasattr(InvoiceIssuedRepository, "update_issued_record")
    assert not hasattr(InvoiceIssuedRepository, "delete_issued_record")
    assert not hasattr(InvoiceIssuedRepository, "update")
    assert not hasattr(InvoiceIssuedRepository, "delete")
    assert not hasattr(InvoiceIssuedRepository, "reissue")
    assert not hasattr(InvoiceIssuedRepository, "void")


def test_zero_invoice_amount_persists(db):
    allocation = _seed_allocation(
        db,
        crystallizable=Decimal("0"),
    )
    InvoiceIssuedRepository().create_issued_record(_issued(allocation))

    row = InvoiceIssuedRepository().get_by_invoice_id("INV-ID-001")

    assert row is not None
    assert row["invoice_amount"] == "0"
    assert Decimal(row["invoice_amount"]) == Decimal("0")


def test_invoice_amount_preserved_exactly(db):
    allocation = _seed_allocation(
        db,
        crystallizable=Decimal("1"),
    )
    InvoiceIssuedRepository().create_issued_record(_issued(allocation))

    row = InvoiceIssuedRepository().get_by_invoice_id("INV-ID-001")

    assert row is not None
    assert row["invoice_amount"] == "1"
    assert Decimal(row["invoice_amount"]) == Decimal("1")
    assert Decimal(row["invoice_amount"]) != Decimal("3")
    assert Decimal(row["invoice_amount"]) != Decimal("5")
    assert Decimal(row["invoice_amount"]) != Decimal("15")


def test_no_status_column(db):
    columns = {
        row["name"]
        for row in db.execute(
            "PRAGMA table_info('commercial_invoice_issued_records')"
        ).fetchall()
    }
    assert "status" not in columns
    assert "invoice_status" not in columns
    assert "issued_status" not in columns


def test_no_correction_columns(db):
    columns = {
        row["name"]
        for row in db.execute(
            "PRAGMA table_info('commercial_invoice_issued_records')"
        ).fetchall()
    }
    forbidden = {
        "voided_at",
        "superseded_by",
        "credit_note_id",
        "replacement_invoice_id",
        "cancelled_at",
    }
    assert columns.isdisjoint(forbidden)


def test_no_receivable_due_tax_posting_columns(db):
    columns = {
        row["name"]
        for row in db.execute(
            "PRAGMA table_info('commercial_invoice_issued_records')"
        ).fetchall()
    }
    forbidden = {
        "receivable_id",
        "amount_due",
        "balance_due",
        "due_date",
        "tax_rate",
        "tax_amount",
        "tax_jurisdiction",
        "journal_id",
        "ar_account",
        "revenue_account",
        "payment_status",
        "collection_status",
    }
    assert columns.isdisjoint(forbidden)
