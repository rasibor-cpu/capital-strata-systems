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
from backend.app.persistence.repositories.receivable_credit_repository import (
    ReceivableCreditRepository,
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
    build_invoice_issued_record,
)
from backend.commercialization.performance_crystallization import (
    CrystallizationAssessment,
    CrystallizationFrequency,
    CrystallizationStatus,
    PerformanceCompensationLifecyclePolicy,
)
from backend.commercialization.receivable_credit import (
    CommercialReceivableCreditRecord,
    build_receivable_credit,
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
MIGRATION_022 = Path(
    "backend/app/persistence/migrations/sql/"
    "022_receivable_credit.sql"
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
CREDITED_AT = "2026-04-16T10:00:00+00:00"
CREDITED_AT_2 = "2026-04-17T11:00:00+00:00"


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
        MIGRATION_022,
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


def _seed_recognized(
    connection: sqlite3.Connection,
    *,
    invoice_id: str = "INV-A",
    receivable_id: str = "RECV-001",
    period_start: str = PERIOD_START,
    period_end: str = PERIOD_END,
    crystallizable: Decimal = Decimal("100.00"),
) -> CommercialReceivableRecognitionRecord:
    policy = _policy()
    existing = connection.execute(
        """
        SELECT 1 FROM performance_compensation_terms
        WHERE terms_id = ?
        """,
        (policy.terms_id,),
    ).fetchone()
    if existing is None:
        _create_terms(connection, policy.terms_id)

    existing_policy = connection.execute(
        """
        SELECT 1 FROM performance_compensation_lifecycle_policies
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
        SELECT 1 FROM commercial_billing_profiles
        WHERE billing_profile_id = ?
        """,
        ("BP-001",),
    ).fetchone()
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
    if existing_profile is None:
        BillingProfileRepository().create_profile(profile)

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
    recognition = build_receivable_recognition(
        issued,
        receivable_id=receivable_id,
        recognized_at=RECEIVABLE_AT,
        evidence_refs=("receivable:OPS-1",),
        corrections=(),
    )
    ReceivableRecognitionRepository().create_recognition(recognition)
    return recognition


def _credit(
    receivable: CommercialReceivableRecognitionRecord,
    *,
    credit_id: str = "CR-A",
    credit_amount: Decimal = Decimal("15.00"),
    credited_at: str = CREDITED_AT,
    reason_reference: str = "reason:CREDIT-1",
    evidence_refs: tuple[str, ...] = ("credit:OPS-1",),
) -> CommercialReceivableCreditRecord:
    return build_receivable_credit(
        receivable,
        credit_id=credit_id,
        credit_amount=credit_amount,
        credited_at=credited_at,
        reason_reference=reason_reference,
        evidence_refs=evidence_refs,
    )


def _seed_credit(
    connection: sqlite3.Connection,
    *,
    credit_id: str = "CR-A",
    credit_amount: Decimal = Decimal("15.00"),
    credited_at: str = CREDITED_AT,
    evidence_refs: tuple[str, ...] = ("credit:OPS-1",),
    invoice_id: str = "INV-A",
    receivable_id: str = "RECV-001",
) -> CommercialReceivableCreditRecord:
    receivable = _seed_recognized(
        connection,
        invoice_id=invoice_id,
        receivable_id=receivable_id,
    )
    record = _credit(
        receivable,
        credit_id=credit_id,
        credit_amount=credit_amount,
        credited_at=credited_at,
        evidence_refs=evidence_refs,
    )
    ReceivableCreditRepository().create_credit(record)
    return record


def test_credit_round_trip(db):
    record = _seed_credit(db)
    row = ReceivableCreditRepository().get_by_credit_id("CR-A")
    assert row is not None
    assert row["credit_id"] == "CR-A"
    assert row["receivable_id"] == "RECV-001"
    assert row["invoice_id"] == "INV-A"
    assert row["currency"] == "CAD"
    assert row["credit_amount"] == "15.00"
    assert row["credited_at"] == CREDITED_AT
    assert row["reason_reference"] == "reason:CREDIT-1"
    assert isinstance(record, CommercialReceivableCreditRecord)


def test_exact_decimal_serialization(db):
    _seed_credit(db, credit_amount=Decimal("3.50"))
    row = ReceivableCreditRepository().get_by_credit_id("CR-A")
    assert row is not None
    assert row["credit_amount"] == "3.50"
    assert Decimal(row["credit_amount"]) == Decimal("3.50")


def test_zero_amount_persists(db):
    _seed_credit(db, credit_amount=Decimal("0"))
    row = ReceivableCreditRepository().get_by_credit_id("CR-A")
    assert row is not None
    assert row["credit_amount"] == "0"


def test_evidence_round_trip(db):
    _seed_credit(
        db,
        evidence_refs=("credit:OPS-1", "review:OPS-2"),
    )
    row = ReceivableCreditRepository().get_by_credit_id("CR-A")
    assert row is not None
    assert row["evidence_refs_json"] == (
        '["credit:OPS-1","review:OPS-2"]'
    )
    assert tuple(json.loads(row["evidence_refs_json"])) == (
        "credit:OPS-1",
        "review:OPS-2",
    )


def test_duplicate_credit_id_rejected(db):
    _seed_credit(db, credit_id="CR-A")
    receivable_b = _seed_recognized(
        db,
        invoice_id="INV-B",
        receivable_id="RECV-002",
        period_start=PERIOD_START_2,
        period_end=PERIOD_END_2,
        crystallizable=Decimal("40.00"),
    )
    with pytest.raises(sqlite3.IntegrityError):
        ReceivableCreditRepository().create_credit(
            _credit(receivable_b, credit_id="CR-A")
        )


def test_missing_receivable_fk_rejected(db):
    issued_recognition = _seed_recognized(db)
    record = CommercialReceivableCreditRecord(
        credit_id="CR-A",
        receivable_id="RECV-MISSING",
        invoice_id=issued_recognition.invoice_id,
        currency="CAD",
        credit_amount=Decimal("15.00"),
        credited_at=CREDITED_AT,
        reason_reference="reason:CREDIT-1",
        evidence_refs=("credit:OPS-1",),
    )
    with pytest.raises(sqlite3.IntegrityError):
        ReceivableCreditRepository().create_credit(record)


def test_missing_invoice_fk_rejected(db):
    receivable = _seed_recognized(db)
    record = CommercialReceivableCreditRecord(
        credit_id="CR-A",
        receivable_id=receivable.receivable_id,
        invoice_id="INV-MISSING",
        currency="CAD",
        credit_amount=Decimal("15.00"),
        credited_at=CREDITED_AT,
        reason_reference="reason:CREDIT-1",
        evidence_refs=("credit:OPS-1",),
    )
    with pytest.raises(sqlite3.IntegrityError):
        ReceivableCreditRepository().create_credit(record)


def test_lowercase_currency_rejected(db):
    receivable = _seed_recognized(db)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_receivable_credits (
                credit_id, receivable_id, invoice_id, currency,
                credit_amount, credited_at, reason_reference,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "CR-A",
                receivable.receivable_id,
                receivable.invoice_id,
                "cad",
                "15.00",
                CREDITED_AT,
                "reason:CREDIT-1",
                '["credit:OPS-1"]',
            ),
        )


def test_empty_evidence_rejected(db):
    receivable = _seed_recognized(db)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_receivable_credits (
                credit_id, receivable_id, invoice_id, currency,
                credit_amount, credited_at, reason_reference,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "CR-A",
                receivable.receivable_id,
                receivable.invoice_id,
                "CAD",
                "15.00",
                CREDITED_AT,
                "reason:CREDIT-1",
                "[]",
            ),
        )


def test_blank_reason_reference_rejected(db):
    receivable = _seed_recognized(db)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_receivable_credits (
                credit_id, receivable_id, invoice_id, currency,
                credit_amount, credited_at, reason_reference,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "CR-A",
                receivable.receivable_id,
                receivable.invoice_id,
                "CAD",
                "15.00",
                CREDITED_AT,
                " ",
                '["credit:OPS-1"]',
            ),
        )


def test_multiple_credits_same_receivable_allowed(db):
    receivable = _seed_recognized(db)
    repo = ReceivableCreditRepository()
    repo.create_credit(
        _credit(
            receivable,
            credit_id="CR-A",
            credit_amount=Decimal("10.00"),
            credited_at=CREDITED_AT,
        )
    )
    repo.create_credit(
        _credit(
            receivable,
            credit_id="CR-B",
            credit_amount=Decimal("5.00"),
            credited_at=CREDITED_AT_2,
        )
    )
    rows = repo.get_by_receivable_id("RECV-001")
    assert [row["credit_id"] for row in rows] == ["CR-A", "CR-B"]


def test_multiple_credits_same_invoice_allowed(db):
    receivable = _seed_recognized(db, invoice_id="INV-A")
    repo = ReceivableCreditRepository()
    repo.create_credit(
        _credit(receivable, credit_id="CR-A", credit_amount=Decimal("10.00"))
    )
    repo.create_credit(
        _credit(
            receivable,
            credit_id="CR-B",
            credit_amount=Decimal("5.00"),
            credited_at=CREDITED_AT_2,
        )
    )
    rows = repo.get_by_invoice_id("INV-A")
    assert [row["credit_id"] for row in rows] == ["CR-A", "CR-B"]


def test_deterministic_reads(db):
    receivable = _seed_recognized(db)
    repo = ReceivableCreditRepository()
    repo.create_credit(
        _credit(
            receivable,
            credit_id="CR-B",
            credit_amount=Decimal("5.00"),
            credited_at=CREDITED_AT_2,
        )
    )
    repo.create_credit(
        _credit(
            receivable,
            credit_id="CR-A",
            credit_amount=Decimal("10.00"),
            credited_at=CREDITED_AT,
        )
    )
    listed = repo.list_all()
    assert [row["credit_id"] for row in listed] == ["CR-A", "CR-B"]


def test_no_update_delete_api():
    assert not hasattr(ReceivableCreditRepository, "update_credit")
    assert not hasattr(ReceivableCreditRepository, "delete_credit")
    assert not hasattr(ReceivableCreditRepository, "update")
    assert not hasattr(ReceivableCreditRepository, "delete")


def _table_columns(db) -> set[str]:
    return {
        row["name"]
        for row in db.execute(
            "PRAGMA table_info('commercial_receivable_credits')"
        ).fetchall()
    }


def test_no_credit_note_columns(db):
    columns = _table_columns(db)
    forbidden = {
        "correction_id",
        "credit_note_id",
        "credit_note_number",
        "credit_note_status",
    }
    assert columns.isdisjoint(forbidden)


def test_no_refund_columns(db):
    columns = _table_columns(db)
    forbidden = {"refund_id", "refund_amount", "refund_status"}
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


def test_no_balance_columns(db):
    columns = _table_columns(db)
    forbidden = {
        "outstanding_amount",
        "balance_due",
        "remaining_amount",
        "open_amount",
        "payment_status",
        "collection_status",
    }
    assert columns.isdisjoint(forbidden)


def test_no_raw_credit_bypass_api():
    assert not hasattr(ReceivableCreditRepository, "credit_receivable")
    assert not hasattr(ReceivableCreditRepository, "apply_credit")
    assert not hasattr(ReceivableCreditRepository, "issue_credit_note")
    assert not hasattr(ReceivableCreditRepository, "create_credit_note")
