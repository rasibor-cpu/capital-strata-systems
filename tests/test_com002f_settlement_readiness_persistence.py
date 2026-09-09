from __future__ import annotations

import json
import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest

import backend.app.persistence.repositories.base_repository as base_repository
from backend.app.persistence.repositories.crystallization_assessment_repository import (
    CrystallizationAssessmentRepository,
)
from backend.app.persistence.repositories.performance_compensation_lifecycle_policy_repository import (
    PerformanceCompensationLifecyclePolicyRepository,
)
from backend.app.persistence.repositories.settlement_readiness_repository import (
    SettlementReadinessRepository,
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

UTC_FROM = "2026-01-01T00:00:00+00:00"
UTC_TO = "2026-12-31T00:00:00+00:00"
PERIOD_START = "2026-03-01T00:00:00+00:00"
PERIOD_END = "2026-04-01T00:00:00+00:00"
PERIOD_START_2 = "2026-05-01T00:00:00+00:00"
PERIOD_END_2 = "2026-06-01T00:00:00+00:00"
ASSESSED_AT = "2026-04-01T12:00:00+00:00"
READINESS_AT = "2026-04-02T09:00:00+00:00"


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


def _seed_assessment(
    connection: sqlite3.Connection,
    *,
    policy: PerformanceCompensationLifecyclePolicy | None = None,
    assessment: CrystallizationAssessment | None = None,
) -> CrystallizationAssessment:
    policy = policy or _policy()
    assessment = assessment or _assessment(policy=policy)
    _create_terms(connection, policy.terms_id)
    PerformanceCompensationLifecyclePolicyRepository().create_policy(
        policy
    )
    CrystallizationAssessmentRepository().create_assessment(assessment)
    return assessment


def _readiness(
    assessment: CrystallizationAssessment,
    *,
    status: SettlementReadinessStatus = SettlementReadinessStatus.READY,
    assessed_at: str = READINESS_AT,
    evidence_refs: tuple[str, ...] = ("readiness:OPS-1",),
) -> CommercialSettlementReadiness:
    return build_settlement_readiness(
        assessment,
        status,
        assessed_at,
        evidence_refs,
    )


def _readiness_from_row(row: dict) -> CommercialSettlementReadiness:
    return CommercialSettlementReadiness(
        policy_id=row["policy_id"],
        terms_id=row["terms_id"],
        currency=row["currency"],
        period_start=row["period_start"],
        period_end=row["period_end"],
        crystallizable_amount=Decimal(row["crystallizable_amount"]),
        assessed_at=row["assessed_at"],
        status=SettlementReadinessStatus(row["status"]),
        evidence_refs=tuple(json.loads(row["evidence_refs_json"])),
    )


def test_insert_and_read_ready_readiness(db):
    assessment = _seed_assessment(db)
    readiness = _readiness(assessment)
    SettlementReadinessRepository().create_readiness(readiness)

    row = SettlementReadinessRepository().get_by_period(
        "POLICY-001",
        PERIOD_START,
        PERIOD_END,
    )

    assert row is not None
    assert row["policy_id"] == "POLICY-001"
    assert row["terms_id"] == "TERMS-001"
    assert row["currency"] == "CAD"
    assert row["status"] == "READY"
    assert row["assessed_at"] == READINESS_AT
    assert row["period_start"] == PERIOD_START
    assert row["period_end"] == PERIOD_END


def test_decimal_serialization_is_exact(db):
    assessment = _seed_assessment(
        db,
        assessment=_assessment(
            crystallizable=Decimal("3.50"),
            shadow_total=Decimal("3.50"),
        ),
    )
    SettlementReadinessRepository().create_readiness(
        _readiness(assessment)
    )

    row = SettlementReadinessRepository().get_by_period(
        "POLICY-001",
        PERIOD_START,
        PERIOD_END,
    )

    assert row is not None
    assert row["crystallizable_amount"] == "3.50"
    assert Decimal(row["crystallizable_amount"]) == Decimal("3.50")


def test_status_exact_serialization(db):
    assessment = _seed_assessment(db)
    SettlementReadinessRepository().create_readiness(
        _readiness(
            assessment,
            status=SettlementReadinessStatus.PENDING_APPROVAL,
        )
    )

    row = SettlementReadinessRepository().get_by_period(
        "POLICY-001",
        PERIOD_START,
        PERIOD_END,
    )

    assert row is not None
    assert row["status"] == "PENDING_APPROVAL"
    assert SettlementReadinessStatus(row["status"]) is (
        SettlementReadinessStatus.PENDING_APPROVAL
    )


def test_evidence_json_round_trip(db):
    assessment = _seed_assessment(db)
    SettlementReadinessRepository().create_readiness(
        _readiness(
            assessment,
            evidence_refs=(
                "readiness:OPS-1",
                "acceptance:USER-1",
            ),
        )
    )

    row = SettlementReadinessRepository().get_by_period(
        "POLICY-001",
        PERIOD_START,
        PERIOD_END,
    )

    assert row is not None
    assert row["evidence_refs_json"] == (
        '["readiness:OPS-1","acceptance:USER-1"]'
    )
    assert json.loads(row["evidence_refs_json"]) == [
        "readiness:OPS-1",
        "acceptance:USER-1",
    ]


def test_duplicate_same_period_readiness_rejected(db):
    assessment = _seed_assessment(db)
    repo = SettlementReadinessRepository()
    repo.create_readiness(_readiness(assessment))

    with pytest.raises(sqlite3.IntegrityError):
        repo.create_readiness(
            _readiness(
                assessment,
                status=SettlementReadinessStatus.NOT_READY,
            )
        )


def test_missing_crystallization_assessment_fk_rejected(db):
    _create_terms(db)
    PerformanceCompensationLifecyclePolicyRepository().create_policy(
        _policy()
    )

    readiness = CommercialSettlementReadiness(
        policy_id="POLICY-001",
        terms_id="TERMS-001",
        currency="CAD",
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        crystallizable_amount=Decimal("1"),
        assessed_at=READINESS_AT,
        status=SettlementReadinessStatus.NOT_READY,
        evidence_refs=("readiness:OPS-1",),
    )

    with pytest.raises(sqlite3.IntegrityError):
        SettlementReadinessRepository().create_readiness(readiness)


def test_wrong_period_for_existing_policy_rejected(db):
    assessment = _seed_assessment(db)

    readiness = CommercialSettlementReadiness(
        policy_id=assessment.policy_id,
        terms_id=assessment.terms_id,
        currency=assessment.currency,
        period_start=PERIOD_START_2,
        period_end=PERIOD_END_2,
        crystallizable_amount=assessment.crystallizable_amount,
        assessed_at=READINESS_AT,
        status=SettlementReadinessStatus.NOT_READY,
        evidence_refs=("readiness:OPS-1",),
    )

    with pytest.raises(sqlite3.IntegrityError):
        SettlementReadinessRepository().create_readiness(readiness)


def test_missing_terms_fk_rejected(db):
    assessment = _seed_assessment(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_settlement_readiness (
                policy_id,
                terms_id,
                currency,
                period_start,
                period_end,
                crystallizable_amount,
                assessed_at,
                status,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                assessment.policy_id,
                "MISSING-TERMS",
                assessment.currency,
                assessment.period_start,
                assessment.period_end,
                str(assessment.crystallizable_amount),
                READINESS_AT,
                "NOT_READY",
                '["readiness:OPS-1"]',
            ),
        )


def test_lowercase_currency_rejected(db):
    assessment = _seed_assessment(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_settlement_readiness (
                policy_id,
                terms_id,
                currency,
                period_start,
                period_end,
                crystallizable_amount,
                assessed_at,
                status,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                assessment.policy_id,
                assessment.terms_id,
                "cad",
                assessment.period_start,
                assessment.period_end,
                str(assessment.crystallizable_amount),
                READINESS_AT,
                "READY",
                '["readiness:OPS-1"]',
            ),
        )


def test_invalid_status_rejected_at_db_layer(db):
    assessment = _seed_assessment(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_settlement_readiness (
                policy_id,
                terms_id,
                currency,
                period_start,
                period_end,
                crystallizable_amount,
                assessed_at,
                status,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                assessment.policy_id,
                assessment.terms_id,
                assessment.currency,
                assessment.period_start,
                assessment.period_end,
                str(assessment.crystallizable_amount),
                READINESS_AT,
                "PAID",
                '["readiness:OPS-1"]',
            ),
        )


def test_empty_evidence_rejected(db):
    assessment = _seed_assessment(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO commercial_settlement_readiness (
                policy_id,
                terms_id,
                currency,
                period_start,
                period_end,
                crystallizable_amount,
                assessed_at,
                status,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                assessment.policy_id,
                assessment.terms_id,
                assessment.currency,
                assessment.period_start,
                assessment.period_end,
                str(assessment.crystallizable_amount),
                READINESS_AT,
                "READY",
                "[]",
            ),
        )


def test_get_by_period_is_deterministic(db):
    assessment = _seed_assessment(db)
    SettlementReadinessRepository().create_readiness(
        _readiness(assessment)
    )

    first = SettlementReadinessRepository().get_by_period(
        "POLICY-001",
        PERIOD_START,
        PERIOD_END,
    )
    second = SettlementReadinessRepository().get_by_period(
        "POLICY-001",
        PERIOD_START,
        PERIOD_END,
    )

    assert first is not None
    assert second is not None
    assert first == second
    assert first["status"] == "READY"


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

    repo = SettlementReadinessRepository()
    repo.create_readiness(
        _readiness(
            later,
            status=SettlementReadinessStatus.NOT_READY,
        )
    )
    repo.create_readiness(
        _readiness(
            earlier,
            status=SettlementReadinessStatus.READY,
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
        SettlementReadinessRepository,
        "update_readiness",
    )
    assert not hasattr(
        SettlementReadinessRepository,
        "delete_readiness",
    )
    assert not hasattr(SettlementReadinessRepository, "update")
    assert not hasattr(SettlementReadinessRepository, "delete")


def test_ready_zero_amount_persists(db):
    assessment = _seed_assessment(
        db,
        assessment=_assessment(
            status=CrystallizationStatus.ELIGIBLE,
            shadow_total=Decimal("0"),
            crystallizable=Decimal("0"),
        ),
    )
    SettlementReadinessRepository().create_readiness(
        _readiness(
            assessment,
            status=SettlementReadinessStatus.READY,
        )
    )

    row = SettlementReadinessRepository().get_by_period(
        "POLICY-001",
        PERIOD_START,
        PERIOD_END,
    )

    assert row is not None
    assert row["status"] == "READY"
    assert row["crystallizable_amount"] == "0"
    assert Decimal(row["crystallizable_amount"]) == Decimal("0")


def test_non_ready_status_preserves_crystallizable_amount(db):
    assessment = _seed_assessment(
        db,
        assessment=_assessment(
            crystallizable=Decimal("3.50"),
            shadow_total=Decimal("3.50"),
        ),
    )
    SettlementReadinessRepository().create_readiness(
        _readiness(
            assessment,
            status=SettlementReadinessStatus.BLOCKED,
        )
    )

    row = SettlementReadinessRepository().get_by_period(
        "POLICY-001",
        PERIOD_START,
        PERIOD_END,
    )

    assert row is not None
    assert row["status"] == "BLOCKED"
    assert row["crystallizable_amount"] == "3.50"
    assert Decimal(row["crystallizable_amount"]) == Decimal("3.50")


def test_upstream_amount_preserved_exactly(db):
    assessment = _seed_assessment(
        db,
        assessment=_assessment(
            crystallizable=Decimal("1"),
            shadow_total=Decimal("1"),
        ),
    )
    SettlementReadinessRepository().create_readiness(
        _readiness(assessment)
    )

    row = SettlementReadinessRepository().get_by_period(
        "POLICY-001",
        PERIOD_START,
        PERIOD_END,
    )

    assert row is not None
    assert row["crystallizable_amount"] == "1"
    assert Decimal(row["crystallizable_amount"]) == Decimal("1")
    assert Decimal(row["crystallizable_amount"]) != Decimal("3")
    assert Decimal(row["crystallizable_amount"]) != Decimal("5")
    assert Decimal(row["crystallizable_amount"]) != Decimal("15")


def test_persisted_readiness_has_no_payment_authority(db):
    assessment = _seed_assessment(db)
    SettlementReadinessRepository().create_readiness(
        _readiness(
            assessment,
            status=SettlementReadinessStatus.READY,
        )
    )

    row = SettlementReadinessRepository().get_by_period(
        "POLICY-001",
        PERIOD_START,
        PERIOD_END,
    )

    assert row is not None
    persisted = _readiness_from_row(row)

    assert persisted.real_fee_collection_allowed is False
    assert persisted.client_funds_deduction_allowed is False
    assert persisted.automatic_debit_allowed is False
    assert persisted.invoice_settlement_allowed is False
    assert persisted.money_movement_allowed is False
    assert persisted.broker_withdrawal_allowed is False
    assert persisted.payment_initiation_allowed is False
    assert persisted.execution_authority is False
