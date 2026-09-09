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
from backend.app.persistence.repositories.invoice_correction_repository import (
    InvoiceCorrectionRepository,
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
from backend.commercialization.invoice_correction import (
    CommercialInvoiceCorrectionRecord,
    InvoiceCorrectionType,
    build_invoice_correction,
)
from backend.commercialization.invoice_identity import (
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
MIGRATION_016 = Path(
    "backend/app/persistence/migrations/sql/"
    "016_invoice_correction.sql"
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
CORRECTED_AT = "2026-04-07T14:00:00+00:00"
CORRECTED_AT_2 = "2026-04-08T15:00:00+00:00"


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
        MIGRATION_016,
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


def _policy() -> PerformanceCompensationLifecyclePolicy:
    return PerformanceCompensationLifecyclePolicy(
        policy_id="POLICY-001",
        terms_id="TERMS-001",
        currency="CAD",
        crystallization_frequency=CrystallizationFrequency.QUARTERLY,
        effective_from=UTC_FROM,
        evidence_refs=("policy:POLICY-001",),
        crystallize_on_termination=False,
        effective_to=UTC_TO,
    )


def _assessment(
    *,
    crystallizable: Decimal = Decimal("1"),
    period_start: str = PERIOD_START,
    period_end: str = PERIOD_END,
) -> CrystallizationAssessment:
    policy = _policy()
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


def _seed_issued(
    connection: sqlite3.Connection,
    *,
    invoice_id: str = "INV-A",
    period_start: str = PERIOD_START,
    period_end: str = PERIOD_END,
    crystallizable: Decimal = Decimal("1"),
) -> CommercialInvoiceIssuedRecord:
    policy = _policy()

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

    assessment = _assessment(
        crystallizable=crystallizable,
        period_start=period_start,
        period_end=period_end,
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
        ("BP-001",),
    ).fetchone()
    if existing_profile is None:
        profile = build_commercial_billing_profile(
            billing_profile_id="BP-001",
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
            billing_profile_id="BP-001",
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

    allocation = build_invoice_identity_allocation(
        candidate,
        invoice_id=invoice_id,
        allocated_at=ALLOCATED_AT,
        evidence_refs=("identity:OPS-1",),
    )
    InvoiceIdentityRepository().create_allocation(allocation)

    issued = build_invoice_issued_record(
        allocation,
        issued_at=ISSUED_AT,
        evidence_refs=("issued:OPS-1",),
    )
    InvoiceIssuedRepository().create_issued_record(issued)
    return issued


def test_void_correction_round_trip(db):
    issued = _seed_issued(db, invoice_id="INV-A")
    correction = build_invoice_correction(
        issued,
        correction_id="CORR-001",
        correction_type=InvoiceCorrectionType.VOID,
        corrected_at=CORRECTED_AT,
        reason_reference="reason:VOID-1",
        evidence_refs=("correction:OPS-1",),
    )
    InvoiceCorrectionRepository().create_correction(correction)

    row = InvoiceCorrectionRepository().get_by_correction_id("CORR-001")

    assert row is not None
    assert row["correction_id"] == "CORR-001"
    assert row["invoice_id"] == "INV-A"
    assert row["correction_type"] == "VOID"
    assert row["replacement_invoice_id"] is None
    assert row["reason_reference"] == "reason:VOID-1"


def test_void_replacement_invoice_id_null(db):
    issued = _seed_issued(db)
    InvoiceCorrectionRepository().create_correction(
        build_invoice_correction(
            issued,
            correction_id="CORR-001",
            correction_type=InvoiceCorrectionType.VOID,
            corrected_at=CORRECTED_AT,
            reason_reference="reason:VOID-1",
            evidence_refs=("correction:OPS-1",),
        )
    )
    row = InvoiceCorrectionRepository().get_by_correction_id("CORR-001")
    assert row is not None
    assert row["replacement_invoice_id"] is None


def test_supersede_correction_round_trip(db):
    original = _seed_issued(db, invoice_id="INV-A")
    replacement = _seed_issued(
        db,
        invoice_id="INV-B",
        period_start=PERIOD_START_2,
        period_end=PERIOD_END_2,
        crystallizable=Decimal("2"),
    )
    correction = build_invoice_correction(
        original,
        correction_id="CORR-002",
        correction_type=InvoiceCorrectionType.SUPERSEDE,
        corrected_at=CORRECTED_AT,
        reason_reference="reason:SUPERSEDE-1",
        evidence_refs=("correction:OPS-2",),
        replacement_invoice=replacement,
    )
    InvoiceCorrectionRepository().create_correction(correction)

    row = InvoiceCorrectionRepository().get_by_correction_id("CORR-002")

    assert row is not None
    assert row["correction_type"] == "SUPERSEDE"
    assert row["invoice_id"] == "INV-A"
    assert row["replacement_invoice_id"] == "INV-B"


def test_supersede_replacement_id_exact(db):
    original = _seed_issued(db, invoice_id="INV-A")
    replacement = _seed_issued(
        db,
        invoice_id="INV-B",
        period_start=PERIOD_START_2,
        period_end=PERIOD_END_2,
    )
    InvoiceCorrectionRepository().create_correction(
        build_invoice_correction(
            original,
            correction_id="CORR-002",
            correction_type=InvoiceCorrectionType.SUPERSEDE,
            corrected_at=CORRECTED_AT,
            reason_reference="reason:SUPERSEDE-1",
            evidence_refs=("correction:OPS-2",),
            replacement_invoice=replacement,
        )
    )
    rows = InvoiceCorrectionRepository().get_by_replacement_invoice_id(
        "INV-B"
    )
    assert len(rows) == 1
    assert rows[0]["replacement_invoice_id"] == "INV-B"


def test_duplicate_correction_id_rejected(db):
    issued = _seed_issued(db)
    repo = InvoiceCorrectionRepository()
    correction = build_invoice_correction(
        issued,
        correction_id="CORR-001",
        correction_type=InvoiceCorrectionType.VOID,
        corrected_at=CORRECTED_AT,
        reason_reference="reason:VOID-1",
        evidence_refs=("correction:OPS-1",),
    )
    repo.create_correction(correction)

    with pytest.raises(sqlite3.IntegrityError):
        repo.create_correction(
            build_invoice_correction(
                issued,
                correction_id="CORR-001",
                correction_type=InvoiceCorrectionType.VOID,
                corrected_at=CORRECTED_AT_2,
                reason_reference="reason:VOID-2",
                evidence_refs=("correction:OPS-2",),
            )
        )


def test_missing_original_issued_invoice_fk_rejected(db):
    record = CommercialInvoiceCorrectionRecord(
        correction_id="CORR-001",
        invoice_id="INV-MISSING",
        correction_type=InvoiceCorrectionType.VOID,
        corrected_at=CORRECTED_AT,
        reason_reference="reason:VOID-1",
        evidence_refs=("correction:OPS-1",),
    )
    with pytest.raises(sqlite3.IntegrityError):
        InvoiceCorrectionRepository().create_correction(record)


def test_missing_replacement_issued_invoice_fk_rejected(db):
    original = _seed_issued(db, invoice_id="INV-A")

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_invoice_corrections (
                correction_id,
                invoice_id,
                correction_type,
                corrected_at,
                reason_reference,
                evidence_refs_json,
                replacement_invoice_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "CORR-002",
                original.invoice_id,
                "SUPERSEDE",
                CORRECTED_AT,
                "reason:SUPERSEDE-1",
                '["correction:OPS-2"]',
                "INV-MISSING",
            ),
        )


def test_void_with_replacement_rejected_at_db(db):
    original = _seed_issued(db, invoice_id="INV-A")
    replacement = _seed_issued(
        db,
        invoice_id="INV-B",
        period_start=PERIOD_START_2,
        period_end=PERIOD_END_2,
    )

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_invoice_corrections (
                correction_id,
                invoice_id,
                correction_type,
                corrected_at,
                reason_reference,
                evidence_refs_json,
                replacement_invoice_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "CORR-BAD",
                original.invoice_id,
                "VOID",
                CORRECTED_AT,
                "reason:VOID-1",
                '["correction:OPS-1"]',
                replacement.invoice_id,
            ),
        )


def test_supersede_without_replacement_rejected_at_db(db):
    original = _seed_issued(db, invoice_id="INV-A")

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_invoice_corrections (
                correction_id,
                invoice_id,
                correction_type,
                corrected_at,
                reason_reference,
                evidence_refs_json,
                replacement_invoice_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "CORR-BAD",
                original.invoice_id,
                "SUPERSEDE",
                CORRECTED_AT,
                "reason:SUPERSEDE-1",
                '["correction:OPS-2"]',
                None,
            ),
        )


def test_supersede_with_same_invoice_replacement_rejected(db):
    original = _seed_issued(db, invoice_id="INV-A")

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_invoice_corrections (
                correction_id,
                invoice_id,
                correction_type,
                corrected_at,
                reason_reference,
                evidence_refs_json,
                replacement_invoice_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "CORR-BAD",
                original.invoice_id,
                "SUPERSEDE",
                CORRECTED_AT,
                "reason:SUPERSEDE-1",
                '["correction:OPS-2"]',
                original.invoice_id,
            ),
        )


def test_invalid_correction_type_rejected(db):
    issued = _seed_issued(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_invoice_corrections (
                correction_id,
                invoice_id,
                correction_type,
                corrected_at,
                reason_reference,
                evidence_refs_json,
                replacement_invoice_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "CORR-BAD",
                issued.invoice_id,
                "CREDIT",
                CORRECTED_AT,
                "reason:CREDIT-1",
                '["correction:OPS-1"]',
                None,
            ),
        )


def test_empty_evidence_rejected(db):
    issued = _seed_issued(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_invoice_corrections (
                correction_id,
                invoice_id,
                correction_type,
                corrected_at,
                reason_reference,
                evidence_refs_json,
                replacement_invoice_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "CORR-BAD",
                issued.invoice_id,
                "VOID",
                CORRECTED_AT,
                "reason:VOID-1",
                "[]",
                None,
            ),
        )


def test_blank_reason_reference_rejected(db):
    issued = _seed_issued(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_invoice_corrections (
                correction_id,
                invoice_id,
                correction_type,
                corrected_at,
                reason_reference,
                evidence_refs_json,
                replacement_invoice_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "CORR-BAD",
                issued.invoice_id,
                "VOID",
                CORRECTED_AT,
                " ",
                '["correction:OPS-1"]',
                None,
            ),
        )


def test_deterministic_reads(db):
    issued = _seed_issued(db, invoice_id="INV-A")
    repo = InvoiceCorrectionRepository()
    later = build_invoice_correction(
        issued,
        correction_id="CORR-002",
        correction_type=InvoiceCorrectionType.VOID,
        corrected_at=CORRECTED_AT_2,
        reason_reference="reason:VOID-2",
        evidence_refs=("correction:OPS-2",),
    )
    earlier = build_invoice_correction(
        issued,
        correction_id="CORR-001",
        correction_type=InvoiceCorrectionType.VOID,
        corrected_at=CORRECTED_AT,
        reason_reference="reason:VOID-1",
        evidence_refs=("correction:OPS-1",),
    )
    repo.create_correction(later)
    repo.create_correction(earlier)

    by_invoice = repo.get_by_invoice_id("INV-A")
    listed = repo.list_all()

    assert [row["correction_id"] for row in by_invoice] == [
        "CORR-001",
        "CORR-002",
    ]
    assert [row["correction_id"] for row in listed] == [
        "CORR-001",
        "CORR-002",
    ]


def test_multiple_corrections_for_same_invoice_allowed(db):
    issued = _seed_issued(db, invoice_id="INV-A")
    repo = InvoiceCorrectionRepository()
    repo.create_correction(
        build_invoice_correction(
            issued,
            correction_id="CORR-001",
            correction_type=InvoiceCorrectionType.VOID,
            corrected_at=CORRECTED_AT,
            reason_reference="reason:VOID-1",
            evidence_refs=("correction:OPS-1",),
        )
    )
    repo.create_correction(
        build_invoice_correction(
            issued,
            correction_id="CORR-002",
            correction_type=InvoiceCorrectionType.VOID,
            corrected_at=CORRECTED_AT_2,
            reason_reference="reason:VOID-2",
            evidence_refs=("correction:OPS-2",),
        )
    )
    assert len(repo.get_by_invoice_id("INV-A")) == 2


def test_no_update_delete_api():
    assert not hasattr(InvoiceCorrectionRepository, "update_correction")
    assert not hasattr(InvoiceCorrectionRepository, "delete_correction")
    assert not hasattr(InvoiceCorrectionRepository, "update")
    assert not hasattr(InvoiceCorrectionRepository, "delete")
    assert not hasattr(InvoiceCorrectionRepository, "void_invoice")
    assert not hasattr(InvoiceCorrectionRepository, "mutate_invoice")


def test_no_credit_accounting_columns(db):
    columns = {
        row["name"]
        for row in db.execute(
            "PRAGMA table_info('commercial_invoice_corrections')"
        ).fetchall()
    }
    forbidden = {
        "credit_amount",
        "credit_note_id",
        "refund_amount",
        "receivable_adjustment",
        "revenue_reversal",
        "journal_id",
        "ar_account",
        "payment_status",
        "collection_status",
        "voided_at",
        "superseded_status",
    }
    assert columns.isdisjoint(forbidden)


def test_no_issued_invoice_mutation(db):
    issued = _seed_issued(db, invoice_id="INV-A")
    before = InvoiceIssuedRepository().get_by_invoice_id("INV-A")
    assert before is not None

    InvoiceCorrectionRepository().create_correction(
        build_invoice_correction(
            issued,
            correction_id="CORR-001",
            correction_type=InvoiceCorrectionType.VOID,
            corrected_at=CORRECTED_AT,
            reason_reference="reason:VOID-1",
            evidence_refs=("correction:OPS-1",),
        )
    )

    after = InvoiceIssuedRepository().get_by_invoice_id("INV-A")
    assert after is not None
    assert dict(after) == dict(before)
    assert after["invoice_amount"] == before["invoice_amount"]
    assert "status" not in after


def test_evidence_round_trip(db):
    issued = _seed_issued(db)
    InvoiceCorrectionRepository().create_correction(
        build_invoice_correction(
            issued,
            correction_id="CORR-001",
            correction_type=InvoiceCorrectionType.VOID,
            corrected_at=CORRECTED_AT,
            reason_reference="reason:VOID-1",
            evidence_refs=("correction:OPS-1", "review:OPS-2"),
        )
    )
    row = InvoiceCorrectionRepository().get_by_correction_id("CORR-001")
    assert row is not None
    assert row["evidence_refs_json"] == (
        '["correction:OPS-1","review:OPS-2"]'
    )
    assert tuple(json.loads(row["evidence_refs_json"])) == (
        "correction:OPS-1",
        "review:OPS-2",
    )
