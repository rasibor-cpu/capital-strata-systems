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
from backend.app.persistence.repositories.crystallization_assessment_repository import (
    CrystallizationAssessmentRepository,
)
from backend.app.persistence.repositories.performance_compensation_lifecycle_policy_repository import (
    PerformanceCompensationLifecyclePolicyRepository,
)
from backend.app.persistence.repositories.settlement_readiness_repository import (
    SettlementReadinessRepository,
)
from backend.commercialization.billable_obligation import (
    BillableObligationStatus,
    CommercialBillableObligation,
    build_billable_obligation,
)
from backend.commercialization.performance_crystallization import (
    CrystallizationAssessment,
    CrystallizationFrequency,
    CrystallizationStatus,
    PerformanceCompensationLifecyclePolicy,
)
from backend.commercialization.settlement_readiness import (
    CommercialSettlementReadiness,
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

UTC_FROM = "2026-01-01T00:00:00+00:00"
UTC_TO = "2026-12-31T00:00:00+00:00"
PERIOD_START = "2026-03-01T00:00:00+00:00"
PERIOD_END = "2026-04-01T00:00:00+00:00"
PERIOD_START_2 = "2026-05-01T00:00:00+00:00"
PERIOD_END_2 = "2026-06-01T00:00:00+00:00"
ASSESSED_AT = "2026-04-01T12:00:00+00:00"
READINESS_AT = "2026-04-02T09:00:00+00:00"
RECOGNIZED_AT = "2026-04-03T10:00:00+00:00"


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
        MIGRATION_009.read_text(encoding="utf-8-sig")
    )
    connection.executescript(
        MIGRATION_010.read_text(encoding="utf-8-sig")
    )
    connection.executescript(
        MIGRATION_011.read_text(encoding="utf-8-sig")
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
    currency: str = "CAD",
) -> PerformanceCompensationLifecyclePolicy:
    return PerformanceCompensationLifecyclePolicy(
        policy_id=policy_id,
        terms_id=terms_id,
        currency=currency,
        crystallization_frequency=CrystallizationFrequency.QUARTERLY,
        effective_from=UTC_FROM,
        evidence_refs=("policy:POLICY-001",),
        crystallize_on_termination=False,
        effective_to=UTC_TO,
    )


def _assessment(
    *,
    policy: PerformanceCompensationLifecyclePolicy | None = None,
    status: CrystallizationStatus = CrystallizationStatus.ELIGIBLE,
    shadow_total: Decimal = Decimal("3.50"),
    crystallizable: Decimal | None = None,
    period_start: str = PERIOD_START,
    period_end: str = PERIOD_END,
) -> CrystallizationAssessment:
    policy = policy or _policy()
    if crystallizable is None:
        crystallizable = (
            shadow_total
            if status == CrystallizationStatus.ELIGIBLE
            else Decimal("0")
        )

    return CrystallizationAssessment(
        policy_id=policy.policy_id,
        terms_id=policy.terms_id,
        currency=policy.currency,
        period_start=period_start,
        period_end=period_end,
        assessed_at=ASSESSED_AT,
        shadow_entitlement_total=shadow_total,
        crystallizable_amount=crystallizable,
        status=status,
        evidence_refs=("assessment:Q1",),
    )


def _seed_readiness(
    connection: sqlite3.Connection,
    *,
    policy: PerformanceCompensationLifecyclePolicy | None = None,
    assessment: CrystallizationAssessment | None = None,
    readiness_status: SettlementReadinessStatus = (
        SettlementReadinessStatus.READY
    ),
) -> CommercialSettlementReadiness:
    policy = policy or _policy()
    assessment = assessment or _assessment(policy=policy)
    _create_terms(connection, policy.terms_id)
    PerformanceCompensationLifecyclePolicyRepository().create_policy(
        policy
    )
    CrystallizationAssessmentRepository().create_assessment(assessment)
    readiness = build_settlement_readiness(
        assessment,
        readiness_status,
        READINESS_AT,
        ("readiness:OPS-1",),
    )
    SettlementReadinessRepository().create_readiness(readiness)
    return readiness


def _obligation(
    readiness: CommercialSettlementReadiness,
    *,
    status: BillableObligationStatus = BillableObligationStatus.BILLABLE,
    recognized_at: str = RECOGNIZED_AT,
    evidence_refs: tuple[str, ...] = ("billable:OPS-1",),
) -> CommercialBillableObligation:
    return build_billable_obligation(
        readiness,
        status,
        recognized_at,
        evidence_refs,
    )


def _obligation_from_row(row: dict) -> CommercialBillableObligation:
    return CommercialBillableObligation(
        policy_id=row["policy_id"],
        terms_id=row["terms_id"],
        currency=row["currency"],
        period_start=row["period_start"],
        period_end=row["period_end"],
        billable_amount=Decimal(row["billable_amount"]),
        recognized_at=row["recognized_at"],
        status=BillableObligationStatus(row["status"]),
        evidence_refs=tuple(json.loads(row["evidence_refs_json"])),
    )


def test_insert_and_read_billable_obligation(db):
    readiness = _seed_readiness(db)
    obligation = _obligation(readiness)
    BillableObligationRepository().create_obligation(obligation)

    row = BillableObligationRepository().get_by_period(
        "POLICY-001",
        PERIOD_START,
        PERIOD_END,
    )

    assert row is not None
    assert row["policy_id"] == "POLICY-001"
    assert row["terms_id"] == "TERMS-001"
    assert row["currency"] == "CAD"
    assert row["status"] == "BILLABLE"
    assert row["recognized_at"] == RECOGNIZED_AT
    assert row["period_start"] == PERIOD_START
    assert row["period_end"] == PERIOD_END


def test_decimal_serialization_is_exact(db):
    readiness = _seed_readiness(
        db,
        assessment=_assessment(
            crystallizable=Decimal("3.50"),
            shadow_total=Decimal("3.50"),
        ),
    )
    BillableObligationRepository().create_obligation(
        _obligation(readiness)
    )

    row = BillableObligationRepository().get_by_period(
        "POLICY-001",
        PERIOD_START,
        PERIOD_END,
    )

    assert row is not None
    assert row["billable_amount"] == "3.50"
    assert Decimal(row["billable_amount"]) == Decimal("3.50")


def test_status_exact_serialization(db):
    readiness = _seed_readiness(db)
    BillableObligationRepository().create_obligation(
        _obligation(
            readiness,
            status=BillableObligationStatus.NOT_BILLABLE,
        )
    )

    row = BillableObligationRepository().get_by_period(
        "POLICY-001",
        PERIOD_START,
        PERIOD_END,
    )

    assert row is not None
    assert row["status"] == "NOT_BILLABLE"
    assert BillableObligationStatus(row["status"]) is (
        BillableObligationStatus.NOT_BILLABLE
    )


def test_evidence_json_round_trip(db):
    readiness = _seed_readiness(db)
    BillableObligationRepository().create_obligation(
        _obligation(
            readiness,
            evidence_refs=(
                "billable:OPS-1",
                "acceptance:USER-1",
            ),
        )
    )

    row = BillableObligationRepository().get_by_period(
        "POLICY-001",
        PERIOD_START,
        PERIOD_END,
    )

    assert row is not None
    assert row["evidence_refs_json"] == (
        '["billable:OPS-1","acceptance:USER-1"]'
    )
    assert json.loads(row["evidence_refs_json"]) == [
        "billable:OPS-1",
        "acceptance:USER-1",
    ]


def test_duplicate_same_period_obligation_rejected(db):
    readiness = _seed_readiness(db)
    repo = BillableObligationRepository()
    repo.create_obligation(_obligation(readiness))

    with pytest.raises(sqlite3.IntegrityError):
        repo.create_obligation(
            _obligation(
                readiness,
                status=BillableObligationStatus.NOT_BILLABLE,
            )
        )


def test_missing_readiness_fk_rejected(db):
    assessment = _assessment()
    _create_terms(db, assessment.terms_id)
    PerformanceCompensationLifecyclePolicyRepository().create_policy(
        _policy()
    )
    CrystallizationAssessmentRepository().create_assessment(assessment)

    obligation = CommercialBillableObligation(
        policy_id="POLICY-001",
        terms_id="TERMS-001",
        currency="CAD",
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        billable_amount=Decimal("1"),
        recognized_at=RECOGNIZED_AT,
        status=BillableObligationStatus.NOT_BILLABLE,
        evidence_refs=("billable:OPS-1",),
    )

    with pytest.raises(sqlite3.IntegrityError):
        BillableObligationRepository().create_obligation(obligation)


def test_wrong_period_for_existing_readiness_rejected(db):
    readiness = _seed_readiness(db)

    obligation = CommercialBillableObligation(
        policy_id=readiness.policy_id,
        terms_id=readiness.terms_id,
        currency=readiness.currency,
        period_start=PERIOD_START_2,
        period_end=PERIOD_END_2,
        billable_amount=readiness.crystallizable_amount,
        recognized_at=RECOGNIZED_AT,
        status=BillableObligationStatus.NOT_BILLABLE,
        evidence_refs=("billable:OPS-1",),
    )

    with pytest.raises(sqlite3.IntegrityError):
        BillableObligationRepository().create_obligation(obligation)


def test_missing_terms_fk_rejected(db):
    readiness = _seed_readiness(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_billable_obligations (
                policy_id,
                terms_id,
                currency,
                period_start,
                period_end,
                billable_amount,
                recognized_at,
                status,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                readiness.policy_id,
                "MISSING-TERMS",
                readiness.currency,
                readiness.period_start,
                readiness.period_end,
                str(readiness.crystallizable_amount),
                RECOGNIZED_AT,
                "NOT_BILLABLE",
                '["billable:OPS-1"]',
            ),
        )


def test_lowercase_currency_rejected(db):
    readiness = _seed_readiness(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_billable_obligations (
                policy_id,
                terms_id,
                currency,
                period_start,
                period_end,
                billable_amount,
                recognized_at,
                status,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                readiness.policy_id,
                readiness.terms_id,
                "cad",
                readiness.period_start,
                readiness.period_end,
                str(readiness.crystallizable_amount),
                RECOGNIZED_AT,
                "BILLABLE",
                '["billable:OPS-1"]',
            ),
        )


def test_invalid_status_rejected_at_db_layer(db):
    readiness = _seed_readiness(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_billable_obligations (
                policy_id,
                terms_id,
                currency,
                period_start,
                period_end,
                billable_amount,
                recognized_at,
                status,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                readiness.policy_id,
                readiness.terms_id,
                readiness.currency,
                readiness.period_start,
                readiness.period_end,
                str(readiness.crystallizable_amount),
                RECOGNIZED_AT,
                "INVOICED",
                '["billable:OPS-1"]',
            ),
        )


def test_empty_evidence_rejected(db):
    readiness = _seed_readiness(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_billable_obligations (
                policy_id,
                terms_id,
                currency,
                period_start,
                period_end,
                billable_amount,
                recognized_at,
                status,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                readiness.policy_id,
                readiness.terms_id,
                readiness.currency,
                readiness.period_start,
                readiness.period_end,
                str(readiness.crystallizable_amount),
                RECOGNIZED_AT,
                "BILLABLE",
                "[]",
            ),
        )


def test_get_by_period_is_deterministic(db):
    readiness = _seed_readiness(db)
    BillableObligationRepository().create_obligation(
        _obligation(readiness)
    )

    first = BillableObligationRepository().get_by_period(
        "POLICY-001",
        PERIOD_START,
        PERIOD_END,
    )
    second = BillableObligationRepository().get_by_period(
        "POLICY-001",
        PERIOD_START,
        PERIOD_END,
    )

    assert first is not None
    assert second is not None
    assert first == second
    assert first["status"] == "BILLABLE"


def test_lookup_and_list_are_deterministic(db):
    policy = _policy()
    _create_terms(db, policy.terms_id)
    PerformanceCompensationLifecyclePolicyRepository().create_policy(
        policy
    )

    earlier = _assessment(
        policy=policy,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    )
    later = _assessment(
        policy=policy,
        period_start=PERIOD_START_2,
        period_end=PERIOD_END_2,
        shadow_total=Decimal("1.00"),
        crystallizable=Decimal("1.00"),
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

    repo = BillableObligationRepository()
    repo.create_obligation(
        _obligation(
            later_readiness,
            status=BillableObligationStatus.NOT_BILLABLE,
        )
    )
    repo.create_obligation(
        _obligation(
            earlier_readiness,
            status=BillableObligationStatus.BILLABLE,
        )
    )

    by_policy = repo.get_by_policy_id("POLICY-001")
    by_terms = repo.get_by_terms_id("TERMS-001")
    listed = repo.list_all()

    assert [row["period_start"] for row in by_policy] == [
        PERIOD_START,
        PERIOD_START_2,
    ]
    assert [row["period_start"] for row in by_terms] == [
        PERIOD_START,
        PERIOD_START_2,
    ]
    assert [row["period_start"] for row in listed] == [
        PERIOD_START,
        PERIOD_START_2,
    ]


def test_repository_has_no_mutation_api():
    assert not hasattr(
        BillableObligationRepository,
        "update_obligation",
    )
    assert not hasattr(
        BillableObligationRepository,
        "delete_obligation",
    )
    assert not hasattr(BillableObligationRepository, "update")
    assert not hasattr(BillableObligationRepository, "delete")


def test_billable_zero_amount_persists(db):
    readiness = _seed_readiness(
        db,
        assessment=_assessment(
            status=CrystallizationStatus.ELIGIBLE,
            shadow_total=Decimal("0"),
            crystallizable=Decimal("0"),
        ),
    )
    BillableObligationRepository().create_obligation(
        _obligation(
            readiness,
            status=BillableObligationStatus.BILLABLE,
        )
    )

    row = BillableObligationRepository().get_by_period(
        "POLICY-001",
        PERIOD_START,
        PERIOD_END,
    )

    assert row is not None
    assert row["status"] == "BILLABLE"
    assert row["billable_amount"] == "0"
    assert Decimal(row["billable_amount"]) == Decimal("0")


def test_non_billable_status_preserves_amount(db):
    readiness = _seed_readiness(
        db,
        assessment=_assessment(
            crystallizable=Decimal("3.50"),
            shadow_total=Decimal("3.50"),
        ),
    )
    BillableObligationRepository().create_obligation(
        _obligation(
            readiness,
            status=BillableObligationStatus.BLOCKED,
        )
    )

    row = BillableObligationRepository().get_by_period(
        "POLICY-001",
        PERIOD_START,
        PERIOD_END,
    )

    assert row is not None
    assert row["status"] == "BLOCKED"
    assert row["billable_amount"] == "3.50"
    assert Decimal(row["billable_amount"]) == Decimal("3.50")


def test_upstream_billable_amount_preserved_exactly(db):
    readiness = _seed_readiness(
        db,
        assessment=_assessment(
            crystallizable=Decimal("1"),
            shadow_total=Decimal("1"),
        ),
    )
    BillableObligationRepository().create_obligation(
        _obligation(readiness)
    )

    row = BillableObligationRepository().get_by_period(
        "POLICY-001",
        PERIOD_START,
        PERIOD_END,
    )

    assert row is not None
    assert row["billable_amount"] == "1"
    assert Decimal(row["billable_amount"]) == Decimal("1")
    assert Decimal(row["billable_amount"]) != Decimal("3")
    assert Decimal(row["billable_amount"]) != Decimal("5")
    assert Decimal(row["billable_amount"]) != Decimal("15")


def test_persistence_does_not_create_invoice_semantics():
    assert not hasattr(BillableObligationRepository, "create_invoice")
    assert not hasattr(BillableObligationRepository, "invoice_id")
    assert not hasattr(BillableObligationRepository, "invoice_number")


def test_persistence_does_not_create_receivable_semantics():
    assert not hasattr(
        BillableObligationRepository,
        "create_receivable",
    )
    assert not hasattr(
        BillableObligationRepository,
        "receivable_id",
    )
    assert not hasattr(
        BillableObligationRepository,
        "accounts_receivable",
    )


def test_persistence_does_not_create_ledger_posting_semantics():
    assert not hasattr(BillableObligationRepository, "post_to_ledger")
    assert not hasattr(
        BillableObligationRepository,
        "recognize_revenue",
    )
    assert not hasattr(BillableObligationRepository, "create_journal")


def test_persisted_obligation_has_no_accounting_or_payment_authority(
    db,
):
    readiness = _seed_readiness(db)
    BillableObligationRepository().create_obligation(
        _obligation(
            readiness,
            status=BillableObligationStatus.BILLABLE,
        )
    )

    row = BillableObligationRepository().get_by_period(
        "POLICY-001",
        PERIOD_START,
        PERIOD_END,
    )

    assert row is not None
    persisted = _obligation_from_row(row)

    assert persisted.invoice_creation_allowed is False
    assert persisted.receivable_recognition_allowed is False
    assert persisted.ledger_posting_allowed is False
    assert persisted.revenue_recognition_allowed is False
    assert persisted.tax_calculation_allowed is False
    assert persisted.real_fee_collection_allowed is False
    assert persisted.client_funds_deduction_allowed is False
    assert persisted.automatic_debit_allowed is False
    assert persisted.invoice_settlement_allowed is False
    assert persisted.payment_initiation_allowed is False
    assert persisted.money_movement_allowed is False
    assert persisted.broker_withdrawal_allowed is False
    assert persisted.execution_authority is False
