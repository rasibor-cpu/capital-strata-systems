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
RECEIVABLE_AT_2 = "2026-04-09T16:00:00+00:00"


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
    evidence_refs: tuple[str, ...] = ("receivable:OPS-1",),
) -> CommercialReceivableRecognitionRecord:
    return build_receivable_recognition(
        issued,
        receivable_id=receivable_id,
        recognized_at=recognized_at,
        evidence_refs=evidence_refs,
        corrections=(),
    )


def test_recognition_round_trip(db):
    issued = _seed_issued(db, invoice_id="INV-A")
    record = _recognition(issued)
    ReceivableRecognitionRepository().create_recognition(record)

    row = ReceivableRecognitionRepository().get_by_receivable_id(
        "RECV-001"
    )

    assert row is not None
    assert row["receivable_id"] == "RECV-001"
    assert row["invoice_id"] == "INV-A"
    assert row["billing_profile_id"] == "BP-001"
    assert row["currency"] == "CAD"
    assert row["receivable_amount"] == "1"
    assert row["recognized_at"] == RECEIVABLE_AT


def test_exact_decimal_serialization(db):
    issued = _seed_issued(db, crystallizable=Decimal("3.50"))
    ReceivableRecognitionRepository().create_recognition(
        _recognition(issued)
    )

    row = ReceivableRecognitionRepository().get_by_invoice_id("INV-A")

    assert row is not None
    assert row["receivable_amount"] == "3.50"
    assert Decimal(row["receivable_amount"]) == Decimal("3.50")


def test_evidence_round_trip(db):
    issued = _seed_issued(db)
    ReceivableRecognitionRepository().create_recognition(
        _recognition(
            issued,
            evidence_refs=("receivable:OPS-1", "review:OPS-2"),
        )
    )

    row = ReceivableRecognitionRepository().get_by_receivable_id(
        "RECV-001"
    )

    assert row is not None
    assert row["evidence_refs_json"] == (
        '["receivable:OPS-1","review:OPS-2"]'
    )
    assert tuple(json.loads(row["evidence_refs_json"])) == (
        "receivable:OPS-1",
        "review:OPS-2",
    )


def test_duplicate_receivable_id_rejected(db):
    issued = _seed_issued(db, invoice_id="INV-A")
    issued2 = _seed_issued(
        db,
        invoice_id="INV-B",
        period_start=PERIOD_START_2,
        period_end=PERIOD_END_2,
        crystallizable=Decimal("2"),
    )
    repo = ReceivableRecognitionRepository()
    repo.create_recognition(_recognition(issued, receivable_id="RECV-001"))

    with pytest.raises(sqlite3.IntegrityError):
        repo.create_recognition(
            _recognition(issued2, receivable_id="RECV-001")
        )


def test_duplicate_invoice_id_recognition_rejected(db):
    issued = _seed_issued(db, invoice_id="INV-A")
    repo = ReceivableRecognitionRepository()
    repo.create_recognition(_recognition(issued, receivable_id="RECV-001"))

    with pytest.raises(sqlite3.IntegrityError):
        repo.create_recognition(
            _recognition(issued, receivable_id="RECV-002")
        )


def test_missing_issued_invoice_fk_rejected(db):
    record = CommercialReceivableRecognitionRecord(
        receivable_id="RECV-001",
        invoice_id="INV-MISSING",
        billing_profile_id="BP-001",
        currency="CAD",
        receivable_amount=Decimal("1"),
        recognized_at=RECEIVABLE_AT,
        evidence_refs=("receivable:OPS-1",),
    )
    _seed_issued(db, invoice_id="INV-A")

    with pytest.raises(sqlite3.IntegrityError):
        ReceivableRecognitionRepository().create_recognition(record)


def test_missing_billing_profile_fk_rejected(db):
    issued = _seed_issued(db, invoice_id="INV-A")

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_receivable_recognitions (
                receivable_id,
                invoice_id,
                billing_profile_id,
                currency,
                receivable_amount,
                recognized_at,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "RECV-001",
                issued.invoice_id,
                "BP-MISSING",
                issued.currency,
                str(issued.invoice_amount),
                RECEIVABLE_AT,
                '["receivable:OPS-1"]',
            ),
        )


def test_lowercase_currency_rejected(db):
    issued = _seed_issued(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_receivable_recognitions (
                receivable_id,
                invoice_id,
                billing_profile_id,
                currency,
                receivable_amount,
                recognized_at,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "RECV-001",
                issued.invoice_id,
                issued.billing_profile_id,
                "cad",
                str(issued.invoice_amount),
                RECEIVABLE_AT,
                '["receivable:OPS-1"]',
            ),
        )


def test_empty_evidence_rejected(db):
    issued = _seed_issued(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_receivable_recognitions (
                receivable_id,
                invoice_id,
                billing_profile_id,
                currency,
                receivable_amount,
                recognized_at,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "RECV-001",
                issued.invoice_id,
                issued.billing_profile_id,
                issued.currency,
                str(issued.invoice_amount),
                RECEIVABLE_AT,
                "[]",
            ),
        )


def test_deterministic_reads(db):
    issued_a = _seed_issued(db, invoice_id="INV-A")
    issued_b = _seed_issued(
        db,
        invoice_id="INV-B",
        period_start=PERIOD_START_2,
        period_end=PERIOD_END_2,
        crystallizable=Decimal("2"),
    )
    repo = ReceivableRecognitionRepository()
    repo.create_recognition(
        _recognition(
            issued_b,
            receivable_id="RECV-B",
            recognized_at=RECEIVABLE_AT_2,
        )
    )
    repo.create_recognition(
        _recognition(
            issued_a,
            receivable_id="RECV-A",
            recognized_at=RECEIVABLE_AT,
        )
    )

    by_profile = repo.get_by_billing_profile_id("BP-001")
    listed = repo.list_all()

    assert [row["receivable_id"] for row in by_profile] == [
        "RECV-A",
        "RECV-B",
    ]
    assert [row["receivable_id"] for row in listed] == [
        "RECV-A",
        "RECV-B",
    ]


def test_no_update_delete_api():
    assert not hasattr(
        ReceivableRecognitionRepository,
        "update_recognition",
    )
    assert not hasattr(
        ReceivableRecognitionRepository,
        "delete_recognition",
    )
    assert not hasattr(ReceivableRecognitionRepository, "update")
    assert not hasattr(ReceivableRecognitionRepository, "delete")
    assert not hasattr(
        ReceivableRecognitionRepository,
        "recognize_invoice",
    )
    assert not hasattr(
        ReceivableRecognitionRepository,
        "rerecognize_invoice",
    )


def test_zero_receivable_amount_persists(db):
    issued = _seed_issued(db, crystallizable=Decimal("0"))
    ReceivableRecognitionRepository().create_recognition(
        _recognition(issued)
    )

    row = ReceivableRecognitionRepository().get_by_receivable_id(
        "RECV-001"
    )

    assert row is not None
    assert row["receivable_amount"] == "0"
    assert Decimal(row["receivable_amount"]) == Decimal("0")


def test_exact_amount_preserved(db):
    issued = _seed_issued(db, crystallizable=Decimal("1"))
    ReceivableRecognitionRepository().create_recognition(
        _recognition(issued)
    )

    row = ReceivableRecognitionRepository().get_by_invoice_id("INV-A")

    assert row is not None
    assert row["receivable_amount"] == "1"
    assert Decimal(row["receivable_amount"]) == Decimal("1")
    assert Decimal(row["receivable_amount"]) != Decimal("3")
    assert Decimal(row["receivable_amount"]) != Decimal("5")
    assert Decimal(row["receivable_amount"]) != Decimal("15")


def _table_columns(db) -> set[str]:
    return {
        row["name"]
        for row in db.execute(
            "PRAGMA table_info('commercial_receivable_recognitions')"
        ).fetchall()
    }


def test_no_status_columns(db):
    columns = _table_columns(db)
    assert "status" not in columns
    assert "receivable_status" not in columns


def test_no_balance_columns(db):
    columns = _table_columns(db)
    forbidden = {
        "outstanding_amount",
        "amount_paid",
        "amount_credited",
        "amount_written_off",
        "balance_due",
    }
    assert columns.isdisjoint(forbidden)


def test_no_due_date_columns(db):
    columns = _table_columns(db)
    forbidden = {"due_date", "payment_due_date", "net_days"}
    assert columns.isdisjoint(forbidden)


def test_no_gl_posting_columns(db):
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
        "cash_applied",
        "payment_method",
        "customer_id",
        "client_id",
        "account_id",
    }
    assert columns.isdisjoint(forbidden)


def test_create_path_accepts_validated_domain_record(db):
    issued = _seed_issued(db)
    record = _recognition(issued)
    assert isinstance(record, CommercialReceivableRecognitionRecord)
    ReceivableRecognitionRepository().create_recognition(record)
    row = ReceivableRecognitionRepository().get_by_receivable_id(
        record.receivable_id
    )
    assert row is not None
    assert row["invoice_id"] == record.invoice_id


def test_no_raw_invoice_recognition_bypass_api():
    assert not hasattr(
        ReceivableRecognitionRepository,
        "recognize_invoice",
    )
    assert not hasattr(
        ReceivableRecognitionRepository,
        "create_from_invoice_id",
    )
    assert not hasattr(
        ReceivableRecognitionRepository,
        "build_and_create",
    )
