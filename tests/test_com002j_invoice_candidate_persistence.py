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
    CommercialInvoiceCandidate,
    InvoiceCandidateStatus,
    build_invoice_candidate,
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


def _seed_parents(
    connection: sqlite3.Connection,
    *,
    crystallizable: Decimal = Decimal("1"),
    period_start: str = PERIOD_START,
    period_end: str = PERIOD_END,
    billing_profile_id: str = "BP-001",
    create_obligation: bool = True,
    create_profile: bool = True,
):
    policy = _policy()
    assessment = _assessment(
        policy=policy,
        crystallizable=crystallizable,
        period_start=period_start,
        period_end=period_end,
    )
    _create_terms(connection, policy.terms_id)
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

    obligation = None
    if create_obligation:
        obligation = build_billable_obligation(
            readiness,
            BillableObligationStatus.BILLABLE,
            RECOGNIZED_AT,
            ("billable:OPS-1",),
        )
        BillableObligationRepository().create_obligation(obligation)

    profile = None
    if create_profile:
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

    return obligation, profile


def _candidate(
    obligation,
    profile,
    *,
    status: InvoiceCandidateStatus = InvoiceCandidateStatus.READY,
):
    return build_invoice_candidate(
        obligation,
        profile,
        status,
        CANDIDATE_AT,
        ("candidate:OPS-1",),
    )


def test_ready_candidate_round_trip(db):
    obligation, profile = _seed_parents(db)
    InvoiceCandidateRepository().create_candidate(
        _candidate(obligation, profile)
    )

    row = InvoiceCandidateRepository().get_by_period(
        "POLICY-001",
        PERIOD_START,
        PERIOD_END,
    )

    assert row is not None
    assert row["status"] == "READY"
    assert row["billing_profile_id"] == "BP-001"
    assert row["candidate_amount"] == "1"


def test_not_ready_round_trip(db):
    obligation, profile = _seed_parents(db)
    InvoiceCandidateRepository().create_candidate(
        _candidate(
            obligation,
            profile,
            status=InvoiceCandidateStatus.NOT_READY,
        )
    )

    row = InvoiceCandidateRepository().get_by_period(
        "POLICY-001",
        PERIOD_START,
        PERIOD_END,
    )

    assert row is not None
    assert row["status"] == "NOT_READY"


def test_blocked_round_trip(db):
    obligation, profile = _seed_parents(db)
    InvoiceCandidateRepository().create_candidate(
        _candidate(
            obligation,
            profile,
            status=InvoiceCandidateStatus.BLOCKED,
        )
    )

    row = InvoiceCandidateRepository().get_by_period(
        "POLICY-001",
        PERIOD_START,
        PERIOD_END,
    )

    assert row is not None
    assert row["status"] == "BLOCKED"


def test_expired_round_trip(db):
    obligation, profile = _seed_parents(db)
    InvoiceCandidateRepository().create_candidate(
        _candidate(
            obligation,
            profile,
            status=InvoiceCandidateStatus.EXPIRED,
        )
    )

    row = InvoiceCandidateRepository().get_by_period(
        "POLICY-001",
        PERIOD_START,
        PERIOD_END,
    )

    assert row is not None
    assert row["status"] == "EXPIRED"


def test_exact_decimal_serialization(db):
    obligation, profile = _seed_parents(
        db,
        crystallizable=Decimal("3.50"),
    )
    InvoiceCandidateRepository().create_candidate(
        _candidate(obligation, profile)
    )

    row = InvoiceCandidateRepository().get_by_period(
        "POLICY-001",
        PERIOD_START,
        PERIOD_END,
    )

    assert row is not None
    assert row["candidate_amount"] == "3.50"
    assert Decimal(row["candidate_amount"]) == Decimal("3.50")


def test_evidence_round_trip(db):
    obligation, profile = _seed_parents(db)
    candidate = build_invoice_candidate(
        obligation,
        profile,
        InvoiceCandidateStatus.READY,
        CANDIDATE_AT,
        ("candidate:OPS-1", "review:OPS-2"),
    )
    InvoiceCandidateRepository().create_candidate(candidate)

    row = InvoiceCandidateRepository().get_by_period(
        "POLICY-001",
        PERIOD_START,
        PERIOD_END,
    )

    assert row is not None
    assert row["evidence_refs_json"] == (
        '["candidate:OPS-1","review:OPS-2"]'
    )


def test_duplicate_period_candidate_rejected(db):
    obligation, profile = _seed_parents(db)
    repo = InvoiceCandidateRepository()
    repo.create_candidate(_candidate(obligation, profile))

    with pytest.raises(sqlite3.IntegrityError):
        repo.create_candidate(
            _candidate(
                obligation,
                profile,
                status=InvoiceCandidateStatus.NOT_READY,
            )
        )


def test_missing_billable_obligation_fk_rejected(db):
    _, profile = _seed_parents(db, create_obligation=False)

    candidate = CommercialInvoiceCandidate(
        policy_id="POLICY-001",
        terms_id="TERMS-001",
        billing_profile_id=profile.billing_profile_id,
        currency="CAD",
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        candidate_amount=Decimal("1"),
        assessed_at=CANDIDATE_AT,
        status=InvoiceCandidateStatus.NOT_READY,
        evidence_refs=("candidate:OPS-1",),
    )

    with pytest.raises(sqlite3.IntegrityError):
        InvoiceCandidateRepository().create_candidate(candidate)


def test_wrong_billable_period_rejected(db):
    obligation, profile = _seed_parents(db)

    candidate = CommercialInvoiceCandidate(
        policy_id=obligation.policy_id,
        terms_id=obligation.terms_id,
        billing_profile_id=profile.billing_profile_id,
        currency=obligation.currency,
        period_start=PERIOD_START_2,
        period_end=PERIOD_END_2,
        candidate_amount=obligation.billable_amount,
        assessed_at=CANDIDATE_AT,
        status=InvoiceCandidateStatus.NOT_READY,
        evidence_refs=("candidate:OPS-1",),
    )

    with pytest.raises(sqlite3.IntegrityError):
        InvoiceCandidateRepository().create_candidate(candidate)


def test_missing_billing_profile_fk_rejected(db):
    obligation, _ = _seed_parents(db, create_profile=False)

    candidate = CommercialInvoiceCandidate(
        policy_id=obligation.policy_id,
        terms_id=obligation.terms_id,
        billing_profile_id="BP-MISSING",
        currency=obligation.currency,
        period_start=obligation.period_start,
        period_end=obligation.period_end,
        candidate_amount=obligation.billable_amount,
        assessed_at=CANDIDATE_AT,
        status=InvoiceCandidateStatus.NOT_READY,
        evidence_refs=("candidate:OPS-1",),
    )

    with pytest.raises(sqlite3.IntegrityError):
        InvoiceCandidateRepository().create_candidate(candidate)


def test_missing_terms_fk_rejected(db):
    obligation, profile = _seed_parents(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_invoice_candidates (
                policy_id,
                terms_id,
                billing_profile_id,
                currency,
                period_start,
                period_end,
                candidate_amount,
                assessed_at,
                status,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                obligation.policy_id,
                "MISSING-TERMS",
                profile.billing_profile_id,
                obligation.currency,
                obligation.period_start,
                obligation.period_end,
                str(obligation.billable_amount),
                CANDIDATE_AT,
                "NOT_READY",
                '["candidate:OPS-1"]',
            ),
        )


def test_invalid_status_rejected(db):
    obligation, profile = _seed_parents(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_invoice_candidates (
                policy_id,
                terms_id,
                billing_profile_id,
                currency,
                period_start,
                period_end,
                candidate_amount,
                assessed_at,
                status,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                obligation.policy_id,
                obligation.terms_id,
                profile.billing_profile_id,
                obligation.currency,
                obligation.period_start,
                obligation.period_end,
                str(obligation.billable_amount),
                CANDIDATE_AT,
                "INVOICED",
                '["candidate:OPS-1"]',
            ),
        )


def test_lowercase_currency_rejected(db):
    obligation, profile = _seed_parents(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_invoice_candidates (
                policy_id,
                terms_id,
                billing_profile_id,
                currency,
                period_start,
                period_end,
                candidate_amount,
                assessed_at,
                status,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                obligation.policy_id,
                obligation.terms_id,
                profile.billing_profile_id,
                "cad",
                obligation.period_start,
                obligation.period_end,
                str(obligation.billable_amount),
                CANDIDATE_AT,
                "READY",
                '["candidate:OPS-1"]',
            ),
        )


def test_empty_evidence_rejected(db):
    obligation, profile = _seed_parents(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_invoice_candidates (
                policy_id,
                terms_id,
                billing_profile_id,
                currency,
                period_start,
                period_end,
                candidate_amount,
                assessed_at,
                status,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                obligation.policy_id,
                obligation.terms_id,
                profile.billing_profile_id,
                obligation.currency,
                obligation.period_start,
                obligation.period_end,
                str(obligation.billable_amount),
                CANDIDATE_AT,
                "READY",
                "[]",
            ),
        )


def test_deterministic_reads(db):
    policy = _policy()
    _create_terms(db, policy.terms_id)
    PerformanceCompensationLifecyclePolicyRepository().create_policy(
        policy
    )

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

    earlier = _assessment(
        policy=policy,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        crystallizable=Decimal("1"),
    )
    later = _assessment(
        policy=policy,
        period_start=PERIOD_START_2,
        period_end=PERIOD_END_2,
        crystallizable=Decimal("2"),
    )
    CrystallizationAssessmentRepository().create_assessment(later)
    CrystallizationAssessmentRepository().create_assessment(earlier)

    later_readiness = build_settlement_readiness(
        later,
        SettlementReadinessStatus.READY,
        READINESS_AT,
        ("readiness:OPS-2",),
    )
    earlier_readiness = build_settlement_readiness(
        earlier,
        SettlementReadinessStatus.READY,
        READINESS_AT,
        ("readiness:OPS-1",),
    )
    SettlementReadinessRepository().create_readiness(later_readiness)
    SettlementReadinessRepository().create_readiness(earlier_readiness)

    later_obligation = build_billable_obligation(
        later_readiness,
        BillableObligationStatus.BILLABLE,
        RECOGNIZED_AT,
        ("billable:OPS-2",),
    )
    earlier_obligation = build_billable_obligation(
        earlier_readiness,
        BillableObligationStatus.BILLABLE,
        RECOGNIZED_AT,
        ("billable:OPS-1",),
    )
    BillableObligationRepository().create_obligation(later_obligation)
    BillableObligationRepository().create_obligation(earlier_obligation)

    repo = InvoiceCandidateRepository()
    repo.create_candidate(
        _candidate(
            later_obligation,
            profile,
            status=InvoiceCandidateStatus.NOT_READY,
        )
    )
    repo.create_candidate(
        _candidate(
            earlier_obligation,
            profile,
            status=InvoiceCandidateStatus.READY,
        )
    )

    by_policy = repo.get_by_policy_id("POLICY-001")
    by_terms = repo.get_by_terms_id("TERMS-001")
    by_profile = repo.get_by_billing_profile_id("BP-001")
    listed = repo.list_all()

    expected = [PERIOD_START, PERIOD_START_2]
    assert [row["period_start"] for row in by_policy] == expected
    assert [row["period_start"] for row in by_terms] == expected
    assert [row["period_start"] for row in by_profile] == expected
    assert [row["period_start"] for row in listed] == expected


def test_no_update_delete_api():
    assert not hasattr(InvoiceCandidateRepository, "update_candidate")
    assert not hasattr(InvoiceCandidateRepository, "delete_candidate")
    assert not hasattr(InvoiceCandidateRepository, "update")
    assert not hasattr(InvoiceCandidateRepository, "delete")


def test_zero_amount_ready_persists(db):
    obligation, profile = _seed_parents(
        db,
        crystallizable=Decimal("0"),
    )
    InvoiceCandidateRepository().create_candidate(
        _candidate(obligation, profile)
    )

    row = InvoiceCandidateRepository().get_by_period(
        "POLICY-001",
        PERIOD_START,
        PERIOD_END,
    )

    assert row is not None
    assert row["status"] == "READY"
    assert row["candidate_amount"] == "0"


def test_candidate_amount_preserved_exactly(db):
    obligation, profile = _seed_parents(
        db,
        crystallizable=Decimal("1"),
    )
    InvoiceCandidateRepository().create_candidate(
        _candidate(obligation, profile)
    )

    row = InvoiceCandidateRepository().get_by_period(
        "POLICY-001",
        PERIOD_START,
        PERIOD_END,
    )

    assert row is not None
    assert row["candidate_amount"] == "1"
    assert Decimal(row["candidate_amount"]) != Decimal("3")
    assert Decimal(row["candidate_amount"]) != Decimal("5")
    assert Decimal(row["candidate_amount"]) != Decimal("15")


def test_no_invoice_or_receivable_or_tax_columns(db):
    obligation, profile = _seed_parents(db)
    InvoiceCandidateRepository().create_candidate(
        _candidate(obligation, profile)
    )

    columns = {
        row["name"]
        for row in db.execute(
            "PRAGMA table_info('commercial_invoice_candidates')"
        ).fetchall()
    }

    forbidden = {
        "invoice_candidate_id",
        "invoice_id",
        "invoice_number",
        "invoice_date",
        "issue_date",
        "receivable_id",
        "amount_due",
        "balance_due",
        "due_date",
        "tax_rate",
        "tax_amount",
        "tax_jurisdiction",
        "customer_id",
        "client_id",
        "account_id",
        "payment_status",
        "collection_status",
    }
    assert columns.isdisjoint(forbidden)
