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
from backend.app.persistence.repositories.receivable_recognition_repository import (
    ReceivableRecognitionRepository,
)
from backend.app.persistence.repositories.receivable_reversal_repository import (
    ReceivableReversalRepository,
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
from backend.commercialization.receivable_recognition import (
    CommercialReceivableRecognitionRecord,
    build_receivable_recognition,
)
from backend.commercialization.receivable_reversal import (
    CommercialReceivableReversalRecord,
    build_receivable_reversal,
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
RECEIVABLE_AT = "2026-04-08T15:00:00+00:00"
REVERSED_AT = "2026-04-09T16:00:00+00:00"
REVERSED_AT_2 = "2026-04-10T17:00:00+00:00"


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


def _void_correction(
    issued: CommercialInvoiceIssuedRecord,
    *,
    correction_id: str = "COR-A",
):
    return build_invoice_correction(
        issued,
        correction_id=correction_id,
        correction_type=InvoiceCorrectionType.VOID,
        corrected_at=CORRECTED_AT,
        reason_reference="reason:VOID-1",
        evidence_refs=("correction:OPS-1",),
    )


def _reversal(
    recognition: CommercialReceivableRecognitionRecord,
    correction,
    *,
    reversal_id: str = "REV-001",
    reversed_at: str = REVERSED_AT,
    reason_reference: str = "reason:REV-1",
    evidence_refs: tuple[str, ...] = ("reversal:OPS-1",),
) -> CommercialReceivableReversalRecord:
    return build_receivable_reversal(
        recognition,
        correction,
        reversal_id=reversal_id,
        reversed_at=reversed_at,
        reason_reference=reason_reference,
        evidence_refs=evidence_refs,
    )


def _seed_reversal(
    connection: sqlite3.Connection,
    *,
    invoice_id: str = "INV-A",
    receivable_id: str = "RECV-001",
    correction_id: str = "COR-A",
    reversal_id: str = "REV-001",
    period_start: str = PERIOD_START,
    period_end: str = PERIOD_END,
    crystallizable: Decimal = Decimal("1"),
    reversed_at: str = REVERSED_AT,
    evidence_refs: tuple[str, ...] = ("reversal:OPS-1",),
) -> CommercialReceivableReversalRecord:
    issued, recognition = _seed_recognized(
        connection,
        invoice_id=invoice_id,
        receivable_id=receivable_id,
        period_start=period_start,
        period_end=period_end,
        crystallizable=crystallizable,
    )
    correction = _void_correction(issued, correction_id=correction_id)
    InvoiceCorrectionRepository().create_correction(correction)
    record = _reversal(
        recognition,
        correction,
        reversal_id=reversal_id,
        reversed_at=reversed_at,
        evidence_refs=evidence_refs,
    )
    ReceivableReversalRepository().create_reversal(record)
    return record


def test_reversal_round_trip(db):
    record = _seed_reversal(db)

    row = ReceivableReversalRepository().get_by_reversal_id("REV-001")

    assert row is not None
    assert row["reversal_id"] == "REV-001"
    assert row["receivable_id"] == "RECV-001"
    assert row["invoice_id"] == "INV-A"
    assert row["correction_id"] == "COR-A"
    assert row["currency"] == "CAD"
    assert row["reversal_amount"] == "1"
    assert row["reversed_at"] == REVERSED_AT
    assert row["reason_reference"] == "reason:REV-1"
    assert isinstance(record, CommercialReceivableReversalRecord)


def test_exact_decimal_serialization(db):
    _seed_reversal(db, crystallizable=Decimal("3.50"))

    row = ReceivableReversalRepository().get_by_receivable_id("RECV-001")

    assert row is not None
    assert row["reversal_amount"] == "3.50"
    assert Decimal(row["reversal_amount"]) == Decimal("3.50")


def test_evidence_round_trip(db):
    _seed_reversal(
        db,
        evidence_refs=("reversal:OPS-1", "review:OPS-2"),
    )

    row = ReceivableReversalRepository().get_by_reversal_id("REV-001")

    assert row is not None
    assert row["evidence_refs_json"] == (
        '["reversal:OPS-1","review:OPS-2"]'
    )
    assert tuple(json.loads(row["evidence_refs_json"])) == (
        "reversal:OPS-1",
        "review:OPS-2",
    )


def test_duplicate_reversal_id_rejected(db):
    _seed_reversal(
        db,
        invoice_id="INV-A",
        receivable_id="RECV-001",
        correction_id="COR-A",
        reversal_id="REV-001",
    )
    issued_b, recognition_b = _seed_recognized(
        db,
        invoice_id="INV-B",
        receivable_id="RECV-002",
        period_start=PERIOD_START_2,
        period_end=PERIOD_END_2,
        crystallizable=Decimal("2"),
    )
    correction_b = _void_correction(issued_b, correction_id="COR-B")
    InvoiceCorrectionRepository().create_correction(correction_b)

    with pytest.raises(sqlite3.IntegrityError):
        ReceivableReversalRepository().create_reversal(
            _reversal(
                recognition_b,
                correction_b,
                reversal_id="REV-001",
            )
        )


def test_duplicate_receivable_id_reversal_rejected(db):
    issued, recognition = _seed_recognized(db)
    correction = _void_correction(issued, correction_id="COR-A")
    InvoiceCorrectionRepository().create_correction(correction)
    repo = ReceivableReversalRepository()
    repo.create_reversal(
        _reversal(recognition, correction, reversal_id="REV-001")
    )

    correction_2 = _void_correction(issued, correction_id="COR-B")
    InvoiceCorrectionRepository().create_correction(correction_2)

    with pytest.raises(sqlite3.IntegrityError):
        repo.create_reversal(
            _reversal(
                recognition,
                correction_2,
                reversal_id="REV-002",
            )
        )


def test_missing_receivable_fk_rejected(db):
    issued = _seed_issued(db, invoice_id="INV-A")
    correction = _void_correction(issued)
    InvoiceCorrectionRepository().create_correction(correction)

    record = CommercialReceivableReversalRecord(
        reversal_id="REV-001",
        receivable_id="RECV-MISSING",
        invoice_id=issued.invoice_id,
        correction_id=correction.correction_id,
        currency=issued.currency,
        reversal_amount=issued.invoice_amount,
        reversed_at=REVERSED_AT,
        reason_reference="reason:REV-1",
        evidence_refs=("reversal:OPS-1",),
    )

    with pytest.raises(sqlite3.IntegrityError):
        ReceivableReversalRepository().create_reversal(record)


def test_missing_invoice_fk_rejected(db):
    issued, recognition = _seed_recognized(db)
    correction = _void_correction(issued)
    InvoiceCorrectionRepository().create_correction(correction)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_receivable_reversals (
                reversal_id,
                receivable_id,
                invoice_id,
                correction_id,
                currency,
                reversal_amount,
                reversed_at,
                reason_reference,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "REV-001",
                recognition.receivable_id,
                "INV-MISSING",
                correction.correction_id,
                recognition.currency,
                str(recognition.receivable_amount),
                REVERSED_AT,
                "reason:REV-1",
                '["reversal:OPS-1"]',
            ),
        )


def test_missing_correction_fk_rejected(db):
    issued, recognition = _seed_recognized(db)

    record = CommercialReceivableReversalRecord(
        reversal_id="REV-001",
        receivable_id=recognition.receivable_id,
        invoice_id=recognition.invoice_id,
        correction_id="COR-MISSING",
        currency=recognition.currency,
        reversal_amount=recognition.receivable_amount,
        reversed_at=REVERSED_AT,
        reason_reference="reason:REV-1",
        evidence_refs=("reversal:OPS-1",),
    )

    with pytest.raises(sqlite3.IntegrityError):
        ReceivableReversalRepository().create_reversal(record)


def test_lowercase_currency_rejected(db):
    issued, recognition = _seed_recognized(db)
    correction = _void_correction(issued)
    InvoiceCorrectionRepository().create_correction(correction)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_receivable_reversals (
                reversal_id,
                receivable_id,
                invoice_id,
                correction_id,
                currency,
                reversal_amount,
                reversed_at,
                reason_reference,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "REV-001",
                recognition.receivable_id,
                recognition.invoice_id,
                correction.correction_id,
                "cad",
                str(recognition.receivable_amount),
                REVERSED_AT,
                "reason:REV-1",
                '["reversal:OPS-1"]',
            ),
        )


def test_empty_evidence_rejected(db):
    issued, recognition = _seed_recognized(db)
    correction = _void_correction(issued)
    InvoiceCorrectionRepository().create_correction(correction)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_receivable_reversals (
                reversal_id,
                receivable_id,
                invoice_id,
                correction_id,
                currency,
                reversal_amount,
                reversed_at,
                reason_reference,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "REV-001",
                recognition.receivable_id,
                recognition.invoice_id,
                correction.correction_id,
                recognition.currency,
                str(recognition.receivable_amount),
                REVERSED_AT,
                "reason:REV-1",
                "[]",
            ),
        )


def test_blank_reason_reference_rejected(db):
    issued, recognition = _seed_recognized(db)
    correction = _void_correction(issued)
    InvoiceCorrectionRepository().create_correction(correction)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_receivable_reversals (
                reversal_id,
                receivable_id,
                invoice_id,
                correction_id,
                currency,
                reversal_amount,
                reversed_at,
                reason_reference,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "REV-001",
                recognition.receivable_id,
                recognition.invoice_id,
                correction.correction_id,
                recognition.currency,
                str(recognition.receivable_amount),
                REVERSED_AT,
                " ",
                '["reversal:OPS-1"]',
            ),
        )


def test_zero_reversal_amount_persists(db):
    _seed_reversal(db, crystallizable=Decimal("0"))

    row = ReceivableReversalRepository().get_by_reversal_id("REV-001")

    assert row is not None
    assert row["reversal_amount"] == "0"
    assert Decimal(row["reversal_amount"]) == Decimal("0")


def test_exact_amount_preserved(db):
    _seed_reversal(db, crystallizable=Decimal("1"))

    row = ReceivableReversalRepository().get_by_receivable_id("RECV-001")

    assert row is not None
    assert row["reversal_amount"] == "1"
    assert Decimal(row["reversal_amount"]) == Decimal("1")
    assert Decimal(row["reversal_amount"]) != Decimal("-1")
    assert Decimal(row["reversal_amount"]) != Decimal("3")


def test_deterministic_reads(db):
    _seed_reversal(
        db,
        invoice_id="INV-A",
        receivable_id="RECV-A",
        correction_id="COR-A",
        reversal_id="REV-B",
        reversed_at=REVERSED_AT_2,
    )
    issued_b, recognition_b = _seed_recognized(
        db,
        invoice_id="INV-B",
        receivable_id="RECV-B",
        period_start=PERIOD_START_2,
        period_end=PERIOD_END_2,
        crystallizable=Decimal("2"),
    )
    correction_b = _void_correction(issued_b, correction_id="COR-B")
    InvoiceCorrectionRepository().create_correction(correction_b)
    ReceivableReversalRepository().create_reversal(
        _reversal(
            recognition_b,
            correction_b,
            reversal_id="REV-A",
            reversed_at=REVERSED_AT,
        )
    )

    listed = ReceivableReversalRepository().list_all()
    by_invoice_a = ReceivableReversalRepository().get_by_invoice_id(
        "INV-A"
    )
    by_correction_b = (
        ReceivableReversalRepository().get_by_correction_id("COR-B")
    )

    assert [row["reversal_id"] for row in listed] == [
        "REV-A",
        "REV-B",
    ]
    assert [row["reversal_id"] for row in by_invoice_a] == ["REV-B"]
    assert [row["reversal_id"] for row in by_correction_b] == ["REV-A"]


def test_no_update_delete_api():
    assert not hasattr(ReceivableReversalRepository, "update_reversal")
    assert not hasattr(ReceivableReversalRepository, "delete_reversal")
    assert not hasattr(ReceivableReversalRepository, "update")
    assert not hasattr(ReceivableReversalRepository, "delete")
    assert not hasattr(ReceivableReversalRepository, "rereverse")
    assert not hasattr(ReceivableReversalRepository, "replace")


def test_no_raw_reversal_bypass_api():
    assert not hasattr(
        ReceivableReversalRepository,
        "reverse_receivable",
    )
    assert not hasattr(
        ReceivableReversalRepository,
        "reverse_invoice",
    )
    assert not hasattr(
        ReceivableReversalRepository,
        "create_reversal_from_ids",
    )
    assert not hasattr(
        ReceivableReversalRepository,
        "build_and_create",
    )


def _table_columns(db) -> set[str]:
    return {
        row["name"]
        for row in db.execute(
            "PRAGMA table_info('commercial_receivable_reversals')"
        ).fetchall()
    }


def test_no_enum_type_status_columns(db):
    columns = _table_columns(db)
    forbidden = {
        "adjustment_type",
        "reversal_type",
        "status",
        "reversal_status",
    }
    assert columns.isdisjoint(forbidden)


def test_no_partial_adjustment_columns(db):
    columns = _table_columns(db)
    forbidden = {
        "adjustment_amount",
        "partial_amount",
        "remaining_amount",
        "net_amount",
    }
    assert columns.isdisjoint(forbidden)


def test_no_balance_columns(db):
    columns = _table_columns(db)
    forbidden = {
        "outstanding_amount",
        "balance_due",
        "amount_paid",
        "amount_credited",
        "amount_written_off",
    }
    assert columns.isdisjoint(forbidden)


def test_no_gl_columns(db):
    columns = _table_columns(db)
    forbidden = {
        "journal_id",
        "ar_account",
        "revenue_account",
        "debit_account",
        "credit_account",
        "posting_status",
    }
    assert columns.isdisjoint(forbidden)


def test_no_payment_refund_columns(db):
    columns = _table_columns(db)
    forbidden = {
        "credit_amount",
        "credit_note_id",
        "writeoff_amount",
        "bad_debt_amount",
        "refund_amount",
        "payment_status",
        "collection_status",
        "cash_applied",
    }
    assert columns.isdisjoint(forbidden)


def test_create_path_accepts_validated_domain_record(db):
    issued, recognition = _seed_recognized(db)
    correction = _void_correction(issued)
    InvoiceCorrectionRepository().create_correction(correction)
    record = _reversal(recognition, correction)
    assert isinstance(record, CommercialReceivableReversalRecord)
    ReceivableReversalRepository().create_reversal(record)
    row = ReceivableReversalRepository().get_by_reversal_id(
        record.reversal_id
    )
    assert row is not None
    assert row["receivable_id"] == record.receivable_id
    assert row["correction_id"] == record.correction_id
