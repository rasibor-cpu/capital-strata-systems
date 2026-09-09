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
from backend.commercialization.invoice_identity import (
    CommercialInvoiceIdentityAllocation,
    build_invoice_identity_allocation,
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


def _seed_candidate(
    connection: sqlite3.Connection,
    *,
    crystallizable: Decimal = Decimal("1"),
    period_start: str = PERIOD_START,
    period_end: str = PERIOD_END,
    billing_profile_id: str = "BP-001",
    create_terms: bool = True,
    create_profile: bool = True,
    create_candidate: bool = True,
    terms_id: str = "TERMS-001",
    policy_id: str = "POLICY-001",
):
    policy = _policy(policy_id=policy_id, terms_id=terms_id)
    assessment = _assessment(
        policy=policy,
        crystallizable=crystallizable,
        period_start=period_start,
        period_end=period_end,
    )

    if create_terms:
        existing = connection.execute(
            """
            SELECT 1
            FROM performance_compensation_terms
            WHERE terms_id = ?
            """,
            (terms_id,),
        ).fetchone()
        if existing is None:
            _create_terms(connection, terms_id)

        existing_policy = connection.execute(
            """
            SELECT 1
            FROM performance_compensation_lifecycle_policies
            WHERE policy_id = ?
            """,
            (policy_id,),
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

    profile = None
    if create_profile:
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
                terms_id=terms_id,
                party_type=BillingPartyType.ORGANIZATION,
                bill_to_name="Acme Capital Ltd",
                bill_to_reference="BILLTO-ACME-1",
                seller_reference="SELLER-CSS-1",
                tax_treatment_status=TaxTreatmentStatus.OUT_OF_SCOPE,
                payment_terms_status=(
                    PaymentTermsStatus.DEFINED_EXTERNALLY
                ),
                effective_from=UTC_FROM,
                evidence_refs=("profile:BP-001",),
                effective_to=UTC_TO,
            )
            BillingProfileRepository().create_profile(profile)
        else:
            profile = build_commercial_billing_profile(
                billing_profile_id=billing_profile_id,
                terms_id=terms_id,
                party_type=BillingPartyType.ORGANIZATION,
                bill_to_name="Acme Capital Ltd",
                bill_to_reference="BILLTO-ACME-1",
                seller_reference="SELLER-CSS-1",
                tax_treatment_status=TaxTreatmentStatus.OUT_OF_SCOPE,
                payment_terms_status=(
                    PaymentTermsStatus.DEFINED_EXTERNALLY
                ),
                effective_from=UTC_FROM,
                evidence_refs=("profile:BP-001",),
                effective_to=UTC_TO,
            )

    candidate = None
    if create_candidate and profile is not None:
        candidate = build_invoice_candidate(
            obligation,
            profile,
            InvoiceCandidateStatus.READY,
            CANDIDATE_AT,
            ("candidate:OPS-1",),
        )
        InvoiceCandidateRepository().create_candidate(candidate)

    return obligation, profile, candidate


def _allocation(
    candidate: CommercialInvoiceCandidate,
    *,
    invoice_id: str = "INV-ID-001",
    invoice_number: str | None = None,
    evidence_refs: tuple[str, ...] = ("identity:OPS-1",),
) -> CommercialInvoiceIdentityAllocation:
    return build_invoice_identity_allocation(
        candidate,
        invoice_id=invoice_id,
        allocated_at=ALLOCATED_AT,
        evidence_refs=evidence_refs,
        invoice_number=invoice_number,
    )


def test_allocation_with_invoice_number_none_round_trip(db):
    _, _, candidate = _seed_candidate(db)
    InvoiceIdentityRepository().create_allocation(
        _allocation(candidate, invoice_number=None)
    )

    row = InvoiceIdentityRepository().get_by_invoice_id("INV-ID-001")

    assert row is not None
    assert row["invoice_id"] == "INV-ID-001"
    assert row["invoice_number"] is None
    assert row["invoice_amount"] == "1"
    assert row["policy_id"] == "POLICY-001"
    assert row["billing_profile_id"] == "BP-001"


def test_allocation_with_explicit_invoice_number_round_trip(db):
    _, _, candidate = _seed_candidate(db)
    InvoiceIdentityRepository().create_allocation(
        _allocation(candidate, invoice_number="INV-2026-0001")
    )

    row = InvoiceIdentityRepository().get_by_invoice_number(
        "INV-2026-0001"
    )

    assert row is not None
    assert row["invoice_number"] == "INV-2026-0001"
    assert row["invoice_id"] == "INV-ID-001"


def test_exact_decimal_serialization(db):
    _, _, candidate = _seed_candidate(
        db,
        crystallizable=Decimal("3.50"),
    )
    InvoiceIdentityRepository().create_allocation(
        _allocation(candidate)
    )

    row = InvoiceIdentityRepository().get_by_invoice_id("INV-ID-001")

    assert row is not None
    assert row["invoice_amount"] == "3.50"
    assert Decimal(row["invoice_amount"]) == Decimal("3.50")


def test_evidence_round_trip(db):
    _, _, candidate = _seed_candidate(db)
    InvoiceIdentityRepository().create_allocation(
        _allocation(
            candidate,
            evidence_refs=("identity:OPS-1", "review:OPS-2"),
        )
    )

    row = InvoiceIdentityRepository().get_by_invoice_id("INV-ID-001")

    assert row is not None
    assert row["evidence_refs_json"] == (
        '["identity:OPS-1","review:OPS-2"]'
    )
    assert tuple(json.loads(row["evidence_refs_json"])) == (
        "identity:OPS-1",
        "review:OPS-2",
    )


def test_duplicate_invoice_id_rejected(db):
    _, profile, candidate = _seed_candidate(db)
    repo = InvoiceIdentityRepository()
    repo.create_allocation(_allocation(candidate))

    _, _, candidate2 = _seed_candidate(
        db,
        period_start=PERIOD_START_2,
        period_end=PERIOD_END_2,
        create_terms=True,
        create_profile=True,
    )

    with pytest.raises(sqlite3.IntegrityError):
        repo.create_allocation(
            _allocation(candidate2, invoice_id="INV-ID-001")
        )


def test_duplicate_candidate_period_rejected(db):
    _, _, candidate = _seed_candidate(db)
    repo = InvoiceIdentityRepository()
    repo.create_allocation(_allocation(candidate))

    with pytest.raises(sqlite3.IntegrityError):
        repo.create_allocation(
            _allocation(candidate, invoice_id="INV-ID-002")
        )


def test_duplicate_non_null_invoice_number_rejected(db):
    _, _, candidate = _seed_candidate(db)
    repo = InvoiceIdentityRepository()
    repo.create_allocation(
        _allocation(candidate, invoice_number="INV-2026-0001")
    )

    _, _, candidate2 = _seed_candidate(
        db,
        period_start=PERIOD_START_2,
        period_end=PERIOD_END_2,
    )

    with pytest.raises(sqlite3.IntegrityError):
        repo.create_allocation(
            _allocation(
                candidate2,
                invoice_id="INV-ID-002",
                invoice_number="INV-2026-0001",
            )
        )


def test_multiple_null_invoice_number_rows_allowed(db):
    _, _, candidate = _seed_candidate(db)
    _, _, candidate2 = _seed_candidate(
        db,
        period_start=PERIOD_START_2,
        period_end=PERIOD_END_2,
    )
    repo = InvoiceIdentityRepository()
    repo.create_allocation(
        _allocation(candidate, invoice_id="INV-ID-001")
    )
    repo.create_allocation(
        _allocation(candidate2, invoice_id="INV-ID-002")
    )

    listed = repo.list_all()
    assert len(listed) == 2
    assert all(row["invoice_number"] is None for row in listed)


def test_missing_candidate_fk_rejected(db):
    obligation, profile, _ = _seed_candidate(
        db,
        create_candidate=False,
    )
    candidate = CommercialInvoiceCandidate(
        policy_id=obligation.policy_id,
        terms_id=obligation.terms_id,
        billing_profile_id=profile.billing_profile_id,
        currency=obligation.currency,
        period_start=obligation.period_start,
        period_end=obligation.period_end,
        candidate_amount=obligation.billable_amount,
        assessed_at=CANDIDATE_AT,
        status=InvoiceCandidateStatus.READY,
        evidence_refs=("candidate:OPS-1",),
    )

    with pytest.raises(sqlite3.IntegrityError):
        InvoiceIdentityRepository().create_allocation(
            _allocation(candidate)
        )


def test_wrong_candidate_period_rejected(db):
    _, _, candidate = _seed_candidate(db)

    wrong = CommercialInvoiceIdentityAllocation(
        invoice_id="INV-ID-001",
        policy_id=candidate.policy_id,
        terms_id=candidate.terms_id,
        billing_profile_id=candidate.billing_profile_id,
        currency=candidate.currency,
        period_start=PERIOD_START_2,
        period_end=PERIOD_END_2,
        invoice_amount=candidate.candidate_amount,
        allocated_at=ALLOCATED_AT,
        evidence_refs=("identity:OPS-1",),
    )

    with pytest.raises(sqlite3.IntegrityError):
        InvoiceIdentityRepository().create_allocation(wrong)


def test_missing_billing_profile_fk_rejected(db):
    _, _, candidate = _seed_candidate(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_invoice_identity_allocations (
                invoice_id,
                policy_id,
                terms_id,
                billing_profile_id,
                currency,
                period_start,
                period_end,
                invoice_amount,
                allocated_at,
                evidence_refs_json,
                invoice_number
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "INV-ID-001",
                candidate.policy_id,
                candidate.terms_id,
                "BP-MISSING",
                candidate.currency,
                candidate.period_start,
                candidate.period_end,
                str(candidate.candidate_amount),
                ALLOCATED_AT,
                '["identity:OPS-1"]',
                None,
            ),
        )


def test_missing_terms_fk_rejected(db):
    _, _, candidate = _seed_candidate(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_invoice_identity_allocations (
                invoice_id,
                policy_id,
                terms_id,
                billing_profile_id,
                currency,
                period_start,
                period_end,
                invoice_amount,
                allocated_at,
                evidence_refs_json,
                invoice_number
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "INV-ID-001",
                candidate.policy_id,
                "MISSING-TERMS",
                candidate.billing_profile_id,
                candidate.currency,
                candidate.period_start,
                candidate.period_end,
                str(candidate.candidate_amount),
                ALLOCATED_AT,
                '["identity:OPS-1"]',
                None,
            ),
        )


def test_lowercase_currency_rejected(db):
    _, _, candidate = _seed_candidate(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_invoice_identity_allocations (
                invoice_id,
                policy_id,
                terms_id,
                billing_profile_id,
                currency,
                period_start,
                period_end,
                invoice_amount,
                allocated_at,
                evidence_refs_json,
                invoice_number
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "INV-ID-001",
                candidate.policy_id,
                candidate.terms_id,
                candidate.billing_profile_id,
                "cad",
                candidate.period_start,
                candidate.period_end,
                str(candidate.candidate_amount),
                ALLOCATED_AT,
                '["identity:OPS-1"]',
                None,
            ),
        )


def test_blank_invoice_number_rejected_when_non_null(db):
    _, _, candidate = _seed_candidate(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_invoice_identity_allocations (
                invoice_id,
                policy_id,
                terms_id,
                billing_profile_id,
                currency,
                period_start,
                period_end,
                invoice_amount,
                allocated_at,
                evidence_refs_json,
                invoice_number
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "INV-ID-001",
                candidate.policy_id,
                candidate.terms_id,
                candidate.billing_profile_id,
                candidate.currency,
                candidate.period_start,
                candidate.period_end,
                str(candidate.candidate_amount),
                ALLOCATED_AT,
                '["identity:OPS-1"]',
                " ",
            ),
        )


def test_empty_evidence_rejected(db):
    _, _, candidate = _seed_candidate(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_invoice_identity_allocations (
                invoice_id,
                policy_id,
                terms_id,
                billing_profile_id,
                currency,
                period_start,
                period_end,
                invoice_amount,
                allocated_at,
                evidence_refs_json,
                invoice_number
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "INV-ID-001",
                candidate.policy_id,
                candidate.terms_id,
                candidate.billing_profile_id,
                candidate.currency,
                candidate.period_start,
                candidate.period_end,
                str(candidate.candidate_amount),
                ALLOCATED_AT,
                "[]",
                None,
            ),
        )


def test_deterministic_reads(db):
    _, profile, candidate = _seed_candidate(db)
    _, _, candidate2 = _seed_candidate(
        db,
        period_start=PERIOD_START_2,
        period_end=PERIOD_END_2,
        crystallizable=Decimal("2"),
    )
    repo = InvoiceIdentityRepository()
    repo.create_allocation(
        _allocation(candidate2, invoice_id="INV-ID-002")
    )
    repo.create_allocation(
        _allocation(candidate, invoice_id="INV-ID-001")
    )

    by_terms = repo.get_by_terms_id("TERMS-001")
    by_profile = repo.get_by_billing_profile_id("BP-001")
    listed = repo.list_all()
    by_period = repo.get_by_candidate_period(
        "POLICY-001",
        PERIOD_START,
        PERIOD_END,
    )

    expected = [PERIOD_START, PERIOD_START_2]
    assert [row["period_start"] for row in by_terms] == expected
    assert [row["period_start"] for row in by_profile] == expected
    assert [row["period_start"] for row in listed] == expected
    assert by_period is not None
    assert by_period["invoice_id"] == "INV-ID-001"


def test_no_update_delete_api():
    assert not hasattr(InvoiceIdentityRepository, "update_allocation")
    assert not hasattr(InvoiceIdentityRepository, "delete_allocation")
    assert not hasattr(InvoiceIdentityRepository, "update")
    assert not hasattr(InvoiceIdentityRepository, "delete")


def test_zero_invoice_amount_persists(db):
    _, _, candidate = _seed_candidate(
        db,
        crystallizable=Decimal("0"),
    )
    InvoiceIdentityRepository().create_allocation(
        _allocation(candidate)
    )

    row = InvoiceIdentityRepository().get_by_invoice_id("INV-ID-001")

    assert row is not None
    assert row["invoice_amount"] == "0"
    assert Decimal(row["invoice_amount"]) == Decimal("0")


def test_invoice_amount_preserved_exactly(db):
    _, _, candidate = _seed_candidate(
        db,
        crystallizable=Decimal("1"),
    )
    InvoiceIdentityRepository().create_allocation(
        _allocation(candidate)
    )

    row = InvoiceIdentityRepository().get_by_invoice_id("INV-ID-001")

    assert row is not None
    assert row["invoice_amount"] == "1"
    assert Decimal(row["invoice_amount"]) == Decimal("1")
    assert Decimal(row["invoice_amount"]) != Decimal("3")
    assert Decimal(row["invoice_amount"]) != Decimal("5")
    assert Decimal(row["invoice_amount"]) != Decimal("15")


def test_no_invoice_number_generation(db):
    _, _, candidate = _seed_candidate(db)
    allocation = _allocation(candidate, invoice_number=None)
    InvoiceIdentityRepository().create_allocation(allocation)

    row = InvoiceIdentityRepository().get_by_invoice_id("INV-ID-001")

    assert row is not None
    assert row["invoice_number"] is None
    assert not hasattr(
        InvoiceIdentityRepository,
        "generate_invoice_number",
    )
