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
from backend.app.persistence.repositories.receivable_payment_allocation_repository import (
    ReceivablePaymentAllocationRepository,
)
from backend.app.persistence.repositories.receivable_payment_repository import (
    ReceivablePaymentRepository,
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
from backend.commercialization.receivable_payment import (
    CommercialReceivablePaymentRecord,
    build_receivable_payment,
)
from backend.commercialization.receivable_payment_allocation import (
    CommercialReceivablePaymentAllocationRecord,
    build_receivable_payment_allocation,
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
MIGRATION_020 = Path(
    "backend/app/persistence/migrations/sql/"
    "020_receivable_payment.sql"
)
MIGRATION_021 = Path(
    "backend/app/persistence/migrations/sql/"
    "021_receivable_payment_allocation.sql"
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
IDENTITY_AT = "2026-04-05T12:00:00+00:00"
ISSUED_AT = "2026-04-06T13:00:00+00:00"
RECEIVABLE_AT = "2026-04-08T15:00:00+00:00"
OBSERVED_AT = "2026-04-12T18:00:00+00:00"
ALLOCATED_AT = "2026-04-13T19:00:00+00:00"
ALLOCATED_AT_2 = "2026-04-14T20:00:00+00:00"


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
        MIGRATION_020,
        MIGRATION_021,
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
    crystallizable: Decimal = Decimal("100.00"),
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
    crystallizable: Decimal = Decimal("100.00"),
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
        allocated_at=IDENTITY_AT,
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


def _seed_recognized(
    connection: sqlite3.Connection,
    *,
    invoice_id: str = "INV-A",
    receivable_id: str = "RECV-001",
    period_start: str = PERIOD_START,
    period_end: str = PERIOD_END,
    crystallizable: Decimal = Decimal("100.00"),
) -> CommercialReceivableRecognitionRecord:
    issued = _seed_issued(
        connection,
        invoice_id=invoice_id,
        period_start=period_start,
        period_end=period_end,
        crystallizable=crystallizable,
    )
    recognition = build_receivable_recognition(
        issued,
        receivable_id=receivable_id,
        recognized_at=RECEIVABLE_AT,
        evidence_refs=("receivable:OPS-1",),
        corrections=(),
    )
    ReceivableRecognitionRepository().create_recognition(recognition)
    return recognition


def _seed_payment(
    *,
    payment_id: str = "PAY-1",
    payment_amount: Decimal = Decimal("100.00"),
) -> CommercialReceivablePaymentRecord:
    record = build_receivable_payment(
        payment_id=payment_id,
        currency="CAD",
        payment_amount=payment_amount,
        observed_at=OBSERVED_AT,
        external_reference="EXT-REF-001",
        evidence_refs=("payment:OPS-1",),
    )
    ReceivablePaymentRepository().create_payment(record)
    return record


def _allocation(
    payment: CommercialReceivablePaymentRecord,
    receivable: CommercialReceivableRecognitionRecord,
    *,
    allocation_id: str = "ALLOC-A",
    allocated_amount: Decimal = Decimal("60.00"),
    allocated_at: str = ALLOCATED_AT,
    evidence_refs: tuple[str, ...] = ("allocation:OPS-1",),
) -> CommercialReceivablePaymentAllocationRecord:
    return build_receivable_payment_allocation(
        payment,
        receivable,
        allocation_id=allocation_id,
        allocated_amount=allocated_amount,
        allocated_at=allocated_at,
        evidence_refs=evidence_refs,
    )


def _seed_allocation(
    connection: sqlite3.Connection,
    *,
    invoice_id: str = "INV-A",
    receivable_id: str = "RECV-001",
    payment_id: str = "PAY-1",
    allocation_id: str = "ALLOC-A",
    payment_amount: Decimal = Decimal("100.00"),
    allocated_amount: Decimal = Decimal("60.00"),
    allocated_at: str = ALLOCATED_AT,
    evidence_refs: tuple[str, ...] = ("allocation:OPS-1",),
    period_start: str = PERIOD_START,
    period_end: str = PERIOD_END,
    crystallizable: Decimal = Decimal("100.00"),
) -> CommercialReceivablePaymentAllocationRecord:
    receivable = _seed_recognized(
        connection,
        invoice_id=invoice_id,
        receivable_id=receivable_id,
        period_start=period_start,
        period_end=period_end,
        crystallizable=crystallizable,
    )
    payment = _seed_payment(
        payment_id=payment_id,
        payment_amount=payment_amount,
    )
    record = _allocation(
        payment,
        receivable,
        allocation_id=allocation_id,
        allocated_amount=allocated_amount,
        allocated_at=allocated_at,
        evidence_refs=evidence_refs,
    )
    ReceivablePaymentAllocationRepository().create_allocation(record)
    return record


def test_allocation_round_trip(db):
    record = _seed_allocation(db)

    row = ReceivablePaymentAllocationRepository().get_by_allocation_id(
        "ALLOC-A"
    )

    assert row is not None
    assert row["allocation_id"] == "ALLOC-A"
    assert row["payment_id"] == "PAY-1"
    assert row["receivable_id"] == "RECV-001"
    assert row["invoice_id"] == "INV-A"
    assert row["currency"] == "CAD"
    assert row["allocated_amount"] == "60.00"
    assert row["allocated_at"] == ALLOCATED_AT
    assert isinstance(
        record,
        CommercialReceivablePaymentAllocationRecord,
    )


def test_exact_decimal_serialization(db):
    _seed_allocation(
        db,
        payment_amount=Decimal("10.00"),
        allocated_amount=Decimal("3.50"),
    )

    row = ReceivablePaymentAllocationRepository().get_by_allocation_id(
        "ALLOC-A"
    )

    assert row is not None
    assert row["allocated_amount"] == "3.50"
    assert Decimal(row["allocated_amount"]) == Decimal("3.50")


def test_zero_allocation_persists(db):
    _seed_allocation(db, allocated_amount=Decimal("0"))

    row = ReceivablePaymentAllocationRepository().get_by_allocation_id(
        "ALLOC-A"
    )

    assert row is not None
    assert row["allocated_amount"] == "0"
    assert Decimal(row["allocated_amount"]) == Decimal("0")


def test_evidence_round_trip(db):
    _seed_allocation(
        db,
        evidence_refs=("allocation:OPS-1", "review:OPS-2"),
    )

    row = ReceivablePaymentAllocationRepository().get_by_allocation_id(
        "ALLOC-A"
    )

    assert row is not None
    assert row["evidence_refs_json"] == (
        '["allocation:OPS-1","review:OPS-2"]'
    )
    assert tuple(json.loads(row["evidence_refs_json"])) == (
        "allocation:OPS-1",
        "review:OPS-2",
    )


def test_duplicate_allocation_id_rejected(db):
    _seed_allocation(db, allocation_id="ALLOC-A")
    receivable_b = _seed_recognized(
        db,
        invoice_id="INV-B",
        receivable_id="RECV-002",
        period_start=PERIOD_START_2,
        period_end=PERIOD_END_2,
        crystallizable=Decimal("40.00"),
    )
    payment_b = _seed_payment(
        payment_id="PAY-2",
        payment_amount=Decimal("40.00"),
    )

    with pytest.raises(sqlite3.IntegrityError):
        ReceivablePaymentAllocationRepository().create_allocation(
            _allocation(
                payment_b,
                receivable_b,
                allocation_id="ALLOC-A",
                allocated_amount=Decimal("40.00"),
            )
        )


def test_missing_payment_fk_rejected(db):
    receivable = _seed_recognized(db)
    payment = build_receivable_payment(
        payment_id="PAY-MISSING",
        currency="CAD",
        payment_amount=Decimal("60.00"),
        observed_at=OBSERVED_AT,
        external_reference="EXT-MISSING",
        evidence_refs=("payment:OPS-1",),
    )

    with pytest.raises(sqlite3.IntegrityError):
        ReceivablePaymentAllocationRepository().create_allocation(
            _allocation(
                payment,
                receivable,
                allocation_id="ALLOC-A",
                allocated_amount=Decimal("60.00"),
            )
        )


def test_missing_receivable_fk_rejected(db):
    issued = _seed_issued(db)
    payment = _seed_payment()

    record = CommercialReceivablePaymentAllocationRecord(
        allocation_id="ALLOC-A",
        payment_id=payment.payment_id,
        receivable_id="RECV-MISSING",
        invoice_id=issued.invoice_id,
        currency="CAD",
        allocated_amount=Decimal("60.00"),
        allocated_at=ALLOCATED_AT,
        evidence_refs=("allocation:OPS-1",),
    )

    with pytest.raises(sqlite3.IntegrityError):
        ReceivablePaymentAllocationRepository().create_allocation(
            record
        )


def test_missing_invoice_fk_rejected(db):
    receivable = _seed_recognized(db)
    payment = _seed_payment()

    record = CommercialReceivablePaymentAllocationRecord(
        allocation_id="ALLOC-A",
        payment_id=payment.payment_id,
        receivable_id=receivable.receivable_id,
        invoice_id="INV-MISSING",
        currency="CAD",
        allocated_amount=Decimal("60.00"),
        allocated_at=ALLOCATED_AT,
        evidence_refs=("allocation:OPS-1",),
    )

    with pytest.raises(sqlite3.IntegrityError):
        ReceivablePaymentAllocationRepository().create_allocation(
            record
        )


def test_lowercase_currency_rejected(db):
    receivable = _seed_recognized(db)
    payment = _seed_payment()

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_receivable_payment_allocations (
                allocation_id,
                payment_id,
                receivable_id,
                invoice_id,
                currency,
                allocated_amount,
                allocated_at,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "ALLOC-A",
                payment.payment_id,
                receivable.receivable_id,
                receivable.invoice_id,
                "cad",
                "60.00",
                ALLOCATED_AT,
                '["allocation:OPS-1"]',
            ),
        )


def test_empty_evidence_rejected(db):
    receivable = _seed_recognized(db)
    payment = _seed_payment()

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_receivable_payment_allocations (
                allocation_id,
                payment_id,
                receivable_id,
                invoice_id,
                currency,
                allocated_amount,
                allocated_at,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "ALLOC-A",
                payment.payment_id,
                receivable.receivable_id,
                receivable.invoice_id,
                "CAD",
                "60.00",
                ALLOCATED_AT,
                "[]",
            ),
        )


def test_multiple_allocations_for_same_payment_allowed(db):
    receivable_a = _seed_recognized(
        db,
        invoice_id="INV-A",
        receivable_id="RECV-A",
        crystallizable=Decimal("60.00"),
    )
    receivable_b = _seed_recognized(
        db,
        invoice_id="INV-B",
        receivable_id="RECV-B",
        period_start=PERIOD_START_2,
        period_end=PERIOD_END_2,
        crystallizable=Decimal("40.00"),
    )
    payment = _seed_payment(payment_amount=Decimal("100.00"))
    repo = ReceivablePaymentAllocationRepository()

    repo.create_allocation(
        _allocation(
            payment,
            receivable_a,
            allocation_id="ALLOC-A",
            allocated_amount=Decimal("60.00"),
        )
    )
    repo.create_allocation(
        _allocation(
            payment,
            receivable_b,
            allocation_id="ALLOC-B",
            allocated_amount=Decimal("40.00"),
        )
    )

    rows = repo.get_by_payment_id("PAY-1")
    assert [row["allocation_id"] for row in rows] == [
        "ALLOC-A",
        "ALLOC-B",
    ]


def test_multiple_allocations_for_same_receivable_allowed(db):
    receivable = _seed_recognized(db)
    payment_a = _seed_payment(
        payment_id="PAY-A",
        payment_amount=Decimal("30.00"),
    )
    payment_b = _seed_payment(
        payment_id="PAY-B",
        payment_amount=Decimal("40.00"),
    )
    repo = ReceivablePaymentAllocationRepository()

    repo.create_allocation(
        _allocation(
            payment_a,
            receivable,
            allocation_id="ALLOC-A",
            allocated_amount=Decimal("30.00"),
            allocated_at=ALLOCATED_AT,
        )
    )
    repo.create_allocation(
        _allocation(
            payment_b,
            receivable,
            allocation_id="ALLOC-B",
            allocated_amount=Decimal("40.00"),
            allocated_at=ALLOCATED_AT_2,
        )
    )

    rows = repo.get_by_receivable_id("RECV-001")
    assert [row["allocation_id"] for row in rows] == [
        "ALLOC-A",
        "ALLOC-B",
    ]


def test_multiple_allocations_for_same_invoice_allowed(db):
    receivable = _seed_recognized(db, invoice_id="INV-A")
    payment_a = _seed_payment(
        payment_id="PAY-A",
        payment_amount=Decimal("25.00"),
    )
    payment_b = _seed_payment(
        payment_id="PAY-B",
        payment_amount=Decimal("35.00"),
    )
    repo = ReceivablePaymentAllocationRepository()

    repo.create_allocation(
        _allocation(
            payment_a,
            receivable,
            allocation_id="ALLOC-A",
            allocated_amount=Decimal("25.00"),
        )
    )
    repo.create_allocation(
        _allocation(
            payment_b,
            receivable,
            allocation_id="ALLOC-B",
            allocated_amount=Decimal("35.00"),
            allocated_at=ALLOCATED_AT_2,
        )
    )

    rows = repo.get_by_invoice_id("INV-A")
    assert [row["allocation_id"] for row in rows] == [
        "ALLOC-A",
        "ALLOC-B",
    ]


def test_deterministic_reads(db):
    receivable_a = _seed_recognized(
        db,
        invoice_id="INV-A",
        receivable_id="RECV-A",
        crystallizable=Decimal("60.00"),
    )
    receivable_b = _seed_recognized(
        db,
        invoice_id="INV-B",
        receivable_id="RECV-B",
        period_start=PERIOD_START_2,
        period_end=PERIOD_END_2,
        crystallizable=Decimal("40.00"),
    )
    payment = _seed_payment(payment_amount=Decimal("100.00"))
    repo = ReceivablePaymentAllocationRepository()

    repo.create_allocation(
        _allocation(
            payment,
            receivable_a,
            allocation_id="ALLOC-B",
            allocated_amount=Decimal("60.00"),
            allocated_at=ALLOCATED_AT_2,
        )
    )
    repo.create_allocation(
        _allocation(
            payment,
            receivable_b,
            allocation_id="ALLOC-A",
            allocated_amount=Decimal("40.00"),
            allocated_at=ALLOCATED_AT,
        )
    )

    listed = repo.list_all()
    by_payment = repo.get_by_payment_id("PAY-1")

    assert [row["allocation_id"] for row in listed] == [
        "ALLOC-A",
        "ALLOC-B",
    ]
    assert [row["allocation_id"] for row in by_payment] == [
        "ALLOC-A",
        "ALLOC-B",
    ]


def test_no_update_delete_api():
    assert not hasattr(
        ReceivablePaymentAllocationRepository,
        "update_allocation",
    )
    assert not hasattr(
        ReceivablePaymentAllocationRepository,
        "delete_allocation",
    )
    assert not hasattr(ReceivablePaymentAllocationRepository, "update")
    assert not hasattr(ReceivablePaymentAllocationRepository, "delete")


def _table_columns(db) -> set[str]:
    return {
        row["name"]
        for row in db.execute(
            """
            PRAGMA table_info(
                'commercial_receivable_payment_allocations'
            )
            """
        ).fetchall()
    }


def test_no_status_fields(db):
    columns = _table_columns(db)
    forbidden = {
        "status",
        "allocation_status",
        "payment_status",
        "collection_status",
    }
    assert columns.isdisjoint(forbidden)


def test_no_balance_fields(db):
    columns = _table_columns(db)
    forbidden = {
        "outstanding_amount",
        "balance_due",
        "remaining_receivable_amount",
        "remaining_payment_amount",
        "amount_paid_total",
        "open_amount",
        "overpayment_amount",
    }
    assert columns.isdisjoint(forbidden)


def test_no_gl_fields(db):
    columns = _table_columns(db)
    forbidden = {
        "journal_id",
        "cash_account",
        "ar_account",
        "revenue_account",
        "posting_status",
        "cash_posted",
    }
    assert columns.isdisjoint(forbidden)


def test_no_payment_refund_execution_fields(db):
    columns = _table_columns(db)
    forbidden = {
        "credit_amount",
        "credit_note_id",
        "writeoff_amount",
        "refund_amount",
        "refund_status",
        "bank_account",
        "payment_method",
        "transfer_id",
    }
    assert columns.isdisjoint(forbidden)


def test_no_raw_allocation_bypass_api():
    assert not hasattr(
        ReceivablePaymentAllocationRepository,
        "allocate_payment",
    )
    assert not hasattr(
        ReceivablePaymentAllocationRepository,
        "apply_payment",
    )
    assert not hasattr(
        ReceivablePaymentAllocationRepository,
        "cash_apply",
    )
    assert not hasattr(
        ReceivablePaymentAllocationRepository,
        "calculate_open_balance",
    )
    assert not hasattr(
        ReceivablePaymentAllocationRepository,
        "validate_aggregate_allocations",
    )
