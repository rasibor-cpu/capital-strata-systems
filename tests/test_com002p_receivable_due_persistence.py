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
from backend.app.persistence.repositories.receivable_due_repository import (
    ReceivableDueRepository,
)
from backend.app.persistence.repositories.receivable_recognition_repository import (
    ReceivableRecognitionRepository,
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
from backend.commercialization.receivable_due import (
    CommercialReceivableDueRecord,
    build_receivable_due_record,
)
from backend.commercialization.receivable_recognition import (
    CommercialReceivableRecognitionRecord,
    build_receivable_recognition,
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
MIGRATION_017 = Path(
    "backend/app/persistence/migrations/sql/"
    "017_receivable_recognition.sql"
)
MIGRATION_018 = Path(
    "backend/app/persistence/migrations/sql/"
    "018_receivable_reversal.sql"
)
MIGRATION_019 = Path(
    "backend/app/persistence/migrations/sql/"
    "019_receivable_due.sql"
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
RECEIVABLE_AT = "2026-04-08T15:00:00+00:00"
DETERMINED_AT = "2026-04-10T17:00:00+00:00"
DETERMINED_AT_2 = "2026-04-11T18:00:00+00:00"
DUE_DATE = "2026-10-15"


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
        MIGRATION_017,
        MIGRATION_018,
        MIGRATION_019,
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


def _recognition(
    issued: CommercialInvoiceIssuedRecord,
    *,
    receivable_id: str = "RECV-001",
    recognized_at: str = RECEIVABLE_AT,
) -> CommercialReceivableRecognitionRecord:
    return build_receivable_recognition(
        issued,
        receivable_id=receivable_id,
        recognized_at=recognized_at,
        evidence_refs=("receivable:OPS-1",),
        corrections=(),
    )


def _seed_recognized(
    connection: sqlite3.Connection,
    *,
    invoice_id: str = "INV-A",
    receivable_id: str = "RECV-001",
    period_start: str = PERIOD_START,
    period_end: str = PERIOD_END,
    crystallizable: Decimal = Decimal("1"),
) -> tuple[
    CommercialInvoiceIssuedRecord,
    CommercialReceivableRecognitionRecord,
]:
    issued = _seed_issued(
        connection,
        invoice_id=invoice_id,
        period_start=period_start,
        period_end=period_end,
        crystallizable=crystallizable,
    )
    recognition = _recognition(issued, receivable_id=receivable_id)
    ReceivableRecognitionRepository().create_recognition(recognition)
    return issued, recognition


def _due_record(
    recognition: CommercialReceivableRecognitionRecord,
    *,
    due_record_id: str = "DUE-001",
    due_date: str = DUE_DATE,
    determined_at: str = DETERMINED_AT,
    terms_reference: str = "TERMS-EXT-001",
    evidence_refs: tuple[str, ...] = ("due:OPS-1",),
) -> CommercialReceivableDueRecord:
    return build_receivable_due_record(
        recognition,
        due_record_id=due_record_id,
        due_date=due_date,
        determined_at=determined_at,
        terms_reference=terms_reference,
        evidence_refs=evidence_refs,
        reversals=(),
    )


def _seed_due(
    connection: sqlite3.Connection,
    *,
    invoice_id: str = "INV-A",
    receivable_id: str = "RECV-001",
    due_record_id: str = "DUE-001",
    period_start: str = PERIOD_START,
    period_end: str = PERIOD_END,
    crystallizable: Decimal = Decimal("1"),
    due_date: str = DUE_DATE,
    determined_at: str = DETERMINED_AT,
    terms_reference: str = "TERMS-EXT-001",
    evidence_refs: tuple[str, ...] = ("due:OPS-1",),
) -> CommercialReceivableDueRecord:
    _, recognition = _seed_recognized(
        connection,
        invoice_id=invoice_id,
        receivable_id=receivable_id,
        period_start=period_start,
        period_end=period_end,
        crystallizable=crystallizable,
    )
    record = _due_record(
        recognition,
        due_record_id=due_record_id,
        due_date=due_date,
        determined_at=determined_at,
        terms_reference=terms_reference,
        evidence_refs=evidence_refs,
    )
    ReceivableDueRepository().create_due_record(record)
    return record


def test_due_record_round_trip(db):
    record = _seed_due(db)

    row = ReceivableDueRepository().get_by_due_record_id("DUE-001")

    assert row is not None
    assert row["due_record_id"] == "DUE-001"
    assert row["receivable_id"] == "RECV-001"
    assert row["invoice_id"] == "INV-A"
    assert row["due_date"] == DUE_DATE
    assert row["determined_at"] == DETERMINED_AT
    assert row["terms_reference"] == "TERMS-EXT-001"
    assert isinstance(record, CommercialReceivableDueRecord)


def test_due_date_exact_string_round_trip(db):
    _seed_due(db, due_date="2026-09-30")

    row = ReceivableDueRepository().get_by_due_record_id("DUE-001")

    assert row is not None
    assert row["due_date"] == "2026-09-30"
    assert row["due_date"] != "2026-09-30T00:00:00Z"


def test_determined_at_round_trip(db):
    _seed_due(db, determined_at=DETERMINED_AT)

    row = ReceivableDueRepository().get_by_due_record_id("DUE-001")

    assert row is not None
    assert row["determined_at"] == DETERMINED_AT


def test_evidence_round_trip(db):
    _seed_due(
        db,
        evidence_refs=("due:OPS-1", "review:OPS-2"),
    )

    row = ReceivableDueRepository().get_by_due_record_id("DUE-001")

    assert row is not None
    assert row["evidence_refs_json"] == (
        '["due:OPS-1","review:OPS-2"]'
    )
    assert tuple(json.loads(row["evidence_refs_json"])) == (
        "due:OPS-1",
        "review:OPS-2",
    )


def test_terms_reference_round_trip(db):
    _seed_due(db, terms_reference="TERMS-EXT-OPAQUE-9")

    row = ReceivableDueRepository().get_by_due_record_id("DUE-001")

    assert row is not None
    assert row["terms_reference"] == "TERMS-EXT-OPAQUE-9"


def test_duplicate_due_record_id_rejected(db):
    _seed_due(
        db,
        invoice_id="INV-A",
        receivable_id="RECV-001",
        due_record_id="DUE-001",
    )
    _, recognition_b = _seed_recognized(
        db,
        invoice_id="INV-B",
        receivable_id="RECV-002",
        period_start=PERIOD_START_2,
        period_end=PERIOD_END_2,
        crystallizable=Decimal("2"),
    )

    with pytest.raises(sqlite3.IntegrityError):
        ReceivableDueRepository().create_due_record(
            _due_record(
                recognition_b,
                due_record_id="DUE-001",
            )
        )


def test_duplicate_receivable_id_due_record_rejected(db):
    _, recognition = _seed_recognized(db)
    repo = ReceivableDueRepository()
    repo.create_due_record(
        _due_record(recognition, due_record_id="DUE-001")
    )

    with pytest.raises(sqlite3.IntegrityError):
        repo.create_due_record(
            _due_record(recognition, due_record_id="DUE-002")
        )


def test_missing_receivable_fk_rejected(db):
    issued = _seed_issued(db, invoice_id="INV-A")

    record = CommercialReceivableDueRecord(
        due_record_id="DUE-001",
        receivable_id="RECV-MISSING",
        invoice_id=issued.invoice_id,
        due_date=DUE_DATE,
        determined_at=DETERMINED_AT,
        terms_reference="TERMS-EXT-001",
        evidence_refs=("due:OPS-1",),
    )

    with pytest.raises(sqlite3.IntegrityError):
        ReceivableDueRepository().create_due_record(record)


def test_missing_invoice_fk_rejected(db):
    _, recognition = _seed_recognized(db)

    record = CommercialReceivableDueRecord(
        due_record_id="DUE-001",
        receivable_id=recognition.receivable_id,
        invoice_id="INV-MISSING",
        due_date=DUE_DATE,
        determined_at=DETERMINED_AT,
        terms_reference="TERMS-EXT-001",
        evidence_refs=("due:OPS-1",),
    )

    with pytest.raises(sqlite3.IntegrityError):
        ReceivableDueRepository().create_due_record(record)


def test_malformed_due_date_text_rejected(db):
    _, recognition = _seed_recognized(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_receivable_due_records (
                due_record_id,
                receivable_id,
                invoice_id,
                due_date,
                determined_at,
                terms_reference,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "DUE-001",
                recognition.receivable_id,
                recognition.invoice_id,
                "2026-9-30",
                DETERMINED_AT,
                "TERMS-EXT-001",
                '["due:OPS-1"]',
            ),
        )


def test_empty_evidence_rejected(db):
    _, recognition = _seed_recognized(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_receivable_due_records (
                due_record_id,
                receivable_id,
                invoice_id,
                due_date,
                determined_at,
                terms_reference,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "DUE-001",
                recognition.receivable_id,
                recognition.invoice_id,
                DUE_DATE,
                DETERMINED_AT,
                "TERMS-EXT-001",
                "[]",
            ),
        )


def test_blank_terms_reference_rejected(db):
    _, recognition = _seed_recognized(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_receivable_due_records (
                due_record_id,
                receivable_id,
                invoice_id,
                due_date,
                determined_at,
                terms_reference,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "DUE-001",
                recognition.receivable_id,
                recognition.invoice_id,
                DUE_DATE,
                DETERMINED_AT,
                " ",
                '["due:OPS-1"]',
            ),
        )


def test_deterministic_reads(db):
    _seed_due(
        db,
        invoice_id="INV-A",
        receivable_id="RECV-A",
        due_record_id="DUE-B",
        determined_at=DETERMINED_AT_2,
    )
    _, recognition_b = _seed_recognized(
        db,
        invoice_id="INV-B",
        receivable_id="RECV-B",
        period_start=PERIOD_START_2,
        period_end=PERIOD_END_2,
        crystallizable=Decimal("2"),
    )
    ReceivableDueRepository().create_due_record(
        _due_record(
            recognition_b,
            due_record_id="DUE-A",
            determined_at=DETERMINED_AT,
        )
    )

    listed = ReceivableDueRepository().list_all()
    by_invoice_a = ReceivableDueRepository().get_by_invoice_id("INV-A")

    assert [row["due_record_id"] for row in listed] == [
        "DUE-A",
        "DUE-B",
    ]
    assert [row["due_record_id"] for row in by_invoice_a] == ["DUE-B"]


def test_no_update_delete_api():
    assert not hasattr(ReceivableDueRepository, "update_due_record")
    assert not hasattr(ReceivableDueRepository, "delete_due_record")
    assert not hasattr(ReceivableDueRepository, "update")
    assert not hasattr(ReceivableDueRepository, "delete")
    assert not hasattr(ReceivableDueRepository, "replace")
    assert not hasattr(ReceivableDueRepository, "redetermine")


def test_no_raw_due_date_bypass_api():
    assert not hasattr(ReceivableDueRepository, "set_due_date")
    assert not hasattr(ReceivableDueRepository, "determine_due_date")
    assert not hasattr(
        ReceivableDueRepository,
        "create_due_record_from_ids",
    )
    assert not hasattr(ReceivableDueRepository, "build_and_create")


def _table_columns(db) -> set[str]:
    return {
        row["name"]
        for row in db.execute(
            "PRAGMA table_info('commercial_receivable_due_records')"
        ).fetchall()
    }


def test_no_status_columns(db):
    columns = _table_columns(db)
    forbidden = {
        "status",
        "due_status",
        "overdue_status",
        "is_due",
        "is_overdue",
    }
    assert columns.isdisjoint(forbidden)


def test_no_ageing_columns(db):
    columns = _table_columns(db)
    forbidden = {
        "days_overdue",
        "days_outstanding",
        "ageing_bucket",
        "aging_bucket",
    }
    assert columns.isdisjoint(forbidden)


def test_no_balance_columns(db):
    columns = _table_columns(db)
    forbidden = {
        "outstanding_amount",
        "balance_due",
        "amount_due",
        "remaining_amount",
        "amount_paid",
        "amount_credited",
        "amount_written_off",
    }
    assert columns.isdisjoint(forbidden)


def test_no_payment_term_calculator_columns(db):
    columns = _table_columns(db)
    forbidden = {
        "net_days",
        "grace_days",
        "business_days",
        "payment_term_days",
        "holiday_calendar",
    }
    assert columns.isdisjoint(forbidden)


def test_no_gl_columns(db):
    columns = _table_columns(db)
    forbidden = {
        "journal_id",
        "ar_account",
        "revenue_account",
        "posting_status",
    }
    assert columns.isdisjoint(forbidden)


def test_no_payment_collection_columns(db):
    columns = _table_columns(db)
    forbidden = {
        "payment_status",
        "collection_status",
        "payment_method",
        "cash_application",
        "credit_amount",
        "credit_note_id",
        "writeoff_amount",
    }
    assert columns.isdisjoint(forbidden)


def test_create_path_accepts_validated_domain_record(db):
    _, recognition = _seed_recognized(db)
    record = _due_record(recognition)
    assert isinstance(record, CommercialReceivableDueRecord)
    ReceivableDueRepository().create_due_record(record)
    row = ReceivableDueRepository().get_by_due_record_id(
        record.due_record_id
    )
    assert row is not None
    assert row["receivable_id"] == record.receivable_id
    assert row["due_date"] == record.due_date
