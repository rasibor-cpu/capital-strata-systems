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
from backend.commercialization.performance_crystallization import (
    CrystallizationAssessment,
    CrystallizationFrequency,
    CrystallizationStatus,
    PerformanceCompensationLifecyclePolicy,
    build_crystallization_assessment,
)


MIGRATION = Path(
    "backend/app/persistence/migrations/sql/"
    "009_performance_crystallization.sql"
)

UTC_FROM = "2026-01-01T00:00:00+00:00"
UTC_TO = "2026-12-31T00:00:00+00:00"
PERIOD_START = "2026-03-01T00:00:00+00:00"
PERIOD_END = "2026-04-01T00:00:00+00:00"
ASSESSED_AT = "2026-04-01T12:00:00+00:00"


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
        MIGRATION.read_text(encoding="utf-8-sig")
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
    frequency: CrystallizationFrequency = (
        CrystallizationFrequency.QUARTERLY
    ),
    effective_from: str = UTC_FROM,
    effective_to: str | None = UTC_TO,
    evidence_refs: tuple[str, ...] = ("policy:POLICY-001",),
    crystallize_on_termination: bool = False,
) -> PerformanceCompensationLifecyclePolicy:
    return PerformanceCompensationLifecyclePolicy(
        policy_id=policy_id,
        terms_id=terms_id,
        currency=currency,
        crystallization_frequency=frequency,
        effective_from=effective_from,
        evidence_refs=evidence_refs,
        crystallize_on_termination=crystallize_on_termination,
        effective_to=effective_to,
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


def _policy_from_row(row: dict) -> PerformanceCompensationLifecyclePolicy:
    return PerformanceCompensationLifecyclePolicy(
        policy_id=row["policy_id"],
        terms_id=row["terms_id"],
        currency=row["currency"],
        crystallization_frequency=CrystallizationFrequency(
            row["crystallization_frequency"]
        ),
        effective_from=row["effective_from"],
        evidence_refs=tuple(json.loads(row["evidence_refs_json"])),
        crystallize_on_termination=bool(
            row["crystallize_on_termination"]
        ),
        effective_to=row["effective_to"],
    )


def _assessment_from_row(row: dict) -> CrystallizationAssessment:
    return CrystallizationAssessment(
        policy_id=row["policy_id"],
        terms_id=row["terms_id"],
        currency=row["currency"],
        period_start=row["period_start"],
        period_end=row["period_end"],
        assessed_at=row["assessed_at"],
        shadow_entitlement_total=Decimal(
            row["shadow_entitlement_total"]
        ),
        crystallizable_amount=Decimal(
            row["crystallizable_amount"]
        ),
        status=CrystallizationStatus(row["status"]),
        evidence_refs=tuple(json.loads(row["evidence_refs_json"])),
    )


def test_insert_and_read_policy(db):
    _create_terms(db)
    policy = _policy(crystallize_on_termination=True)
    repo = PerformanceCompensationLifecyclePolicyRepository()
    repo.create_policy(policy)

    row = repo.get_by_policy_id("POLICY-001")

    assert row is not None
    assert row["policy_id"] == "POLICY-001"
    assert row["terms_id"] == "TERMS-001"
    assert row["currency"] == "CAD"
    assert row["effective_from"] == UTC_FROM
    assert row["effective_to"] == UTC_TO
    assert row["crystallize_on_termination"] == 1


def test_frequency_enum_exact_serialization(db):
    _create_terms(db)
    repo = PerformanceCompensationLifecyclePolicyRepository()
    repo.create_policy(
        _policy(frequency=CrystallizationFrequency.ANNUALLY)
    )

    row = repo.get_by_policy_id("POLICY-001")

    assert row is not None
    assert row["crystallization_frequency"] == "ANNUALLY"
    assert CrystallizationFrequency(
        row["crystallization_frequency"]
    ) is CrystallizationFrequency.ANNUALLY


def test_policy_evidence_json_round_trip(db):
    _create_terms(db)
    repo = PerformanceCompensationLifecyclePolicyRepository()
    repo.create_policy(
        _policy(
            evidence_refs=(
                "policy:POLICY-001",
                "acceptance:USER-1",
            )
        )
    )

    row = repo.get_by_policy_id("POLICY-001")

    assert row is not None
    assert row["evidence_refs_json"] == (
        '["policy:POLICY-001","acceptance:USER-1"]'
    )
    assert json.loads(row["evidence_refs_json"]) == [
        "policy:POLICY-001",
        "acceptance:USER-1",
    ]


def test_duplicate_policy_rejected(db):
    _create_terms(db)
    repo = PerformanceCompensationLifecyclePolicyRepository()
    repo.create_policy(_policy())

    with pytest.raises(sqlite3.IntegrityError):
        repo.create_policy(_policy())


def test_missing_terms_fk_rejected(db):
    repo = PerformanceCompensationLifecyclePolicyRepository()

    with pytest.raises(sqlite3.IntegrityError):
        repo.create_policy(_policy(terms_id="MISSING-TERMS"))


def test_lowercase_currency_rejected_for_policy(db):
    _create_terms(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO performance_compensation_lifecycle_policies (
                policy_id,
                terms_id,
                currency,
                crystallization_frequency,
                effective_from,
                evidence_refs_json,
                crystallize_on_termination
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "POLICY-LC",
                "TERMS-001",
                "cad",
                "QUARTERLY",
                UTC_FROM,
                '["policy:POLICY-LC"]',
                0,
            ),
        )


def test_invalid_frequency_rejected_at_db_layer(db):
    _create_terms(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO performance_compensation_lifecycle_policies (
                policy_id,
                terms_id,
                currency,
                crystallization_frequency,
                effective_from,
                evidence_refs_json,
                crystallize_on_termination
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "POLICY-BAD-FREQ",
                "TERMS-001",
                "CAD",
                "WEEKLY",
                UTC_FROM,
                '["policy:POLICY-BAD-FREQ"]',
                0,
            ),
        )


def test_empty_policy_evidence_rejected(db):
    _create_terms(db)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO performance_compensation_lifecycle_policies (
                policy_id,
                terms_id,
                currency,
                crystallization_frequency,
                effective_from,
                evidence_refs_json,
                crystallize_on_termination
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "POLICY-EMPTY",
                "TERMS-001",
                "CAD",
                "QUARTERLY",
                UTC_FROM,
                "[]",
                0,
            ),
        )


def test_crystallize_on_termination_persists_exact_boolean(db):
    _create_terms(db)
    repo = PerformanceCompensationLifecyclePolicyRepository()
    repo.create_policy(
        _policy(
            policy_id="POLICY-TRUE",
            crystallize_on_termination=True,
        )
    )
    repo.create_policy(
        _policy(
            policy_id="POLICY-FALSE",
            crystallize_on_termination=False,
        )
    )

    true_row = repo.get_by_policy_id("POLICY-TRUE")
    false_row = repo.get_by_policy_id("POLICY-FALSE")

    assert true_row is not None
    assert false_row is not None
    assert true_row["crystallize_on_termination"] == 1
    assert false_row["crystallize_on_termination"] == 0
    assert _policy_from_row(true_row).crystallize_on_termination is True
    assert (
        _policy_from_row(false_row).crystallize_on_termination
        is False
    )


def test_policy_repository_has_no_mutation_api():
    assert not hasattr(
        PerformanceCompensationLifecyclePolicyRepository,
        "update_policy",
    )
    assert not hasattr(
        PerformanceCompensationLifecyclePolicyRepository,
        "delete_policy",
    )
    assert not hasattr(
        PerformanceCompensationLifecyclePolicyRepository,
        "update",
    )
    assert not hasattr(
        PerformanceCompensationLifecyclePolicyRepository,
        "delete",
    )


def test_insert_and_read_eligible_assessment(db):
    _create_terms(db)
    policy = _policy()
    PerformanceCompensationLifecyclePolicyRepository().create_policy(
        policy
    )

    assessment = _assessment(policy=policy)
    repo = CrystallizationAssessmentRepository()
    repo.create_assessment(assessment)

    row = repo.get_by_period(
        "POLICY-001",
        PERIOD_START,
        PERIOD_END,
    )

    assert row is not None
    assert row["policy_id"] == "POLICY-001"
    assert row["terms_id"] == "TERMS-001"
    assert row["currency"] == "CAD"
    assert row["status"] == "ELIGIBLE"
    assert row["assessed_at"] == ASSESSED_AT


def test_assessment_decimal_serialization_is_exact(db):
    _create_terms(db)
    policy = _policy()
    PerformanceCompensationLifecyclePolicyRepository().create_policy(
        policy
    )

    CrystallizationAssessmentRepository().create_assessment(
        _assessment(
            policy=policy,
            shadow_total=Decimal("3.50"),
            crystallizable=Decimal("3.50"),
            status=CrystallizationStatus.ELIGIBLE,
        )
    )

    row = CrystallizationAssessmentRepository().get_by_period(
        "POLICY-001",
        PERIOD_START,
        PERIOD_END,
    )

    assert row is not None
    assert row["shadow_entitlement_total"] == "3.50"
    assert row["crystallizable_amount"] == "3.50"
    assert Decimal(row["shadow_entitlement_total"]) == Decimal("3.50")
    assert Decimal(row["crystallizable_amount"]) == Decimal("3.50")


def test_blocked_assessment_persists_zero_crystallizable_amount(db):
    _create_terms(db)
    policy = _policy()
    PerformanceCompensationLifecyclePolicyRepository().create_policy(
        policy
    )

    CrystallizationAssessmentRepository().create_assessment(
        _assessment(
            policy=policy,
            status=CrystallizationStatus.BLOCKED,
            shadow_total=Decimal("3.50"),
            crystallizable=Decimal("0"),
        )
    )

    row = CrystallizationAssessmentRepository().get_by_period(
        "POLICY-001",
        PERIOD_START,
        PERIOD_END,
    )

    assert row is not None
    assert row["status"] == "BLOCKED"
    assert row["shadow_entitlement_total"] == "3.50"
    assert row["crystallizable_amount"] == "0"
    assert Decimal(row["crystallizable_amount"]) == Decimal("0")


def test_status_exact_serialization(db):
    _create_terms(db)
    policy = _policy()
    PerformanceCompensationLifecyclePolicyRepository().create_policy(
        policy
    )

    CrystallizationAssessmentRepository().create_assessment(
        _assessment(
            policy=policy,
            status=CrystallizationStatus.NOT_DUE,
            crystallizable=Decimal("0"),
        )
    )

    row = CrystallizationAssessmentRepository().get_by_period(
        "POLICY-001",
        PERIOD_START,
        PERIOD_END,
    )

    assert row is not None
    assert row["status"] == "NOT_DUE"
    assert CrystallizationStatus(row["status"]) is (
        CrystallizationStatus.NOT_DUE
    )


def test_assessment_evidence_json_round_trip(db):
    _create_terms(db)
    policy = _policy()
    PerformanceCompensationLifecyclePolicyRepository().create_policy(
        policy
    )

    assessment = CrystallizationAssessment(
        policy_id=policy.policy_id,
        terms_id=policy.terms_id,
        currency=policy.currency,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        assessed_at=ASSESSED_AT,
        shadow_entitlement_total=Decimal("0"),
        crystallizable_amount=Decimal("0"),
        status=CrystallizationStatus.ELIGIBLE,
        evidence_refs=("assessment:Q1", "review:OPS-1"),
    )
    CrystallizationAssessmentRepository().create_assessment(assessment)

    row = CrystallizationAssessmentRepository().get_by_period(
        "POLICY-001",
        PERIOD_START,
        PERIOD_END,
    )

    assert row is not None
    assert row["evidence_refs_json"] == (
        '["assessment:Q1","review:OPS-1"]'
    )


def test_duplicate_assessment_same_policy_period_rejected(db):
    _create_terms(db)
    policy = _policy()
    PerformanceCompensationLifecyclePolicyRepository().create_policy(
        policy
    )
    repo = CrystallizationAssessmentRepository()
    repo.create_assessment(_assessment(policy=policy))

    with pytest.raises(sqlite3.IntegrityError):
        repo.create_assessment(
            _assessment(
                policy=policy,
                status=CrystallizationStatus.BLOCKED,
                crystallizable=Decimal("0"),
            )
        )


def test_missing_policy_fk_rejected(db):
    _create_terms(db)

    with pytest.raises(sqlite3.IntegrityError):
        CrystallizationAssessmentRepository().create_assessment(
            _assessment()
        )


def test_missing_terms_fk_for_assessment_rejected(db):
    _create_terms(db, "TERMS-001")
    policy = _policy(terms_id="TERMS-001")
    PerformanceCompensationLifecyclePolicyRepository().create_policy(
        policy
    )

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO crystallization_assessments (
                policy_id,
                terms_id,
                currency,
                period_start,
                period_end,
                assessed_at,
                shadow_entitlement_total,
                crystallizable_amount,
                status,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "POLICY-001",
                "MISSING-TERMS",
                "CAD",
                PERIOD_START,
                PERIOD_END,
                ASSESSED_AT,
                "0",
                "0",
                "ELIGIBLE",
                '["assessment:Q1"]',
            ),
        )


def test_lowercase_currency_rejected_for_assessment(db):
    _create_terms(db)
    PerformanceCompensationLifecyclePolicyRepository().create_policy(
        _policy()
    )

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO crystallization_assessments (
                policy_id,
                terms_id,
                currency,
                period_start,
                period_end,
                assessed_at,
                shadow_entitlement_total,
                crystallizable_amount,
                status,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "POLICY-001",
                "TERMS-001",
                "cad",
                PERIOD_START,
                PERIOD_END,
                ASSESSED_AT,
                "0",
                "0",
                "ELIGIBLE",
                '["assessment:Q1"]',
            ),
        )


def test_invalid_status_rejected_at_db_layer(db):
    _create_terms(db)
    PerformanceCompensationLifecyclePolicyRepository().create_policy(
        _policy()
    )

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO crystallization_assessments (
                policy_id,
                terms_id,
                currency,
                period_start,
                period_end,
                assessed_at,
                shadow_entitlement_total,
                crystallizable_amount,
                status,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "POLICY-001",
                "TERMS-001",
                "CAD",
                PERIOD_START,
                PERIOD_END,
                ASSESSED_AT,
                "0",
                "0",
                "PAID",
                '["assessment:Q1"]',
            ),
        )


def test_assessment_lookup_and_list_are_deterministic(db):
    _create_terms(db)
    policy = _policy()
    PerformanceCompensationLifecyclePolicyRepository().create_policy(
        policy
    )

    repo = CrystallizationAssessmentRepository()
    later = _assessment(
        policy=policy,
        period_start="2026-05-01T00:00:00+00:00",
        period_end="2026-06-01T00:00:00+00:00",
    )
    earlier = _assessment(
        policy=policy,
        period_start="2026-03-01T00:00:00+00:00",
        period_end="2026-04-01T00:00:00+00:00",
    )

    repo.create_assessment(later)
    repo.create_assessment(earlier)

    by_policy = repo.get_by_policy_id("POLICY-001")
    assert [row["period_start"] for row in by_policy] == [
        "2026-03-01T00:00:00+00:00",
        "2026-05-01T00:00:00+00:00",
    ]
    assert [row["period_start"] for row in repo.list_all()] == [
        "2026-03-01T00:00:00+00:00",
        "2026-05-01T00:00:00+00:00",
    ]


def test_assessment_repository_has_no_mutation_api():
    assert not hasattr(
        CrystallizationAssessmentRepository,
        "update_assessment",
    )
    assert not hasattr(
        CrystallizationAssessmentRepository,
        "delete_assessment",
    )
    assert not hasattr(
        CrystallizationAssessmentRepository,
        "update",
    )
    assert not hasattr(
        CrystallizationAssessmentRepository,
        "delete",
    )


def test_persisted_objects_have_no_fee_or_money_movement_authority(db):
    _create_terms(db)
    policy = _policy()
    PerformanceCompensationLifecyclePolicyRepository().create_policy(
        policy
    )
    CrystallizationAssessmentRepository().create_assessment(
        _assessment(policy=policy)
    )

    policy_row = (
        PerformanceCompensationLifecyclePolicyRepository().get_by_policy_id(
            "POLICY-001"
        )
    )
    assessment_row = CrystallizationAssessmentRepository().get_by_period(
        "POLICY-001",
        PERIOD_START,
        PERIOD_END,
    )

    assert policy_row is not None
    assert assessment_row is not None

    persisted_policy = _policy_from_row(policy_row)
    persisted_assessment = _assessment_from_row(assessment_row)

    assert persisted_policy.real_fee_collection_allowed is False
    assert persisted_assessment.real_fee_collection_allowed is False
    assert persisted_policy.client_funds_deduction_allowed is False
    assert persisted_assessment.client_funds_deduction_allowed is False
    assert persisted_policy.automatic_debit_allowed is False
    assert persisted_assessment.automatic_debit_allowed is False
    assert persisted_policy.invoice_settlement_allowed is False
    assert persisted_assessment.invoice_settlement_allowed is False
    assert persisted_policy.money_movement_allowed is False
    assert persisted_assessment.money_movement_allowed is False
    assert persisted_policy.execution_authority is False
    assert persisted_assessment.execution_authority is False


def test_builder_path_persists_only_shadow_totals(db):
    _create_terms(db)
    policy = _policy()
    PerformanceCompensationLifecyclePolicyRepository().create_policy(
        policy
    )

    from backend.commercialization.performance_compensation import (
        ShadowCompensationEntitlement,
    )

    entitlements = (
        ShadowCompensationEntitlement(
            trade_id="TRADE-001",
            terms_id="TERMS-001",
            currency="CAD",
            new_economic_gain=Decimal("5"),
            compensation_rate=Decimal("0.20"),
            shadow_compensation_amount=Decimal("1.00"),
            calculation_timestamp="2026-03-15T10:00:00Z",
            evidence_refs=("agreement:TERMS-001",),
        ),
        ShadowCompensationEntitlement(
            trade_id="TRADE-002",
            terms_id="TERMS-001",
            currency="CAD",
            new_economic_gain=Decimal("12.5"),
            compensation_rate=Decimal("0.20"),
            shadow_compensation_amount=Decimal("2.50"),
            calculation_timestamp="2026-03-20T10:00:00Z",
            evidence_refs=("agreement:TERMS-001",),
        ),
    )

    assessment = build_crystallization_assessment(
        policy,
        entitlements,
        PERIOD_START,
        PERIOD_END,
        ASSESSED_AT,
        CrystallizationStatus.ELIGIBLE,
        ("assessment:Q1",),
    )

    CrystallizationAssessmentRepository().create_assessment(assessment)
    row = CrystallizationAssessmentRepository().get_by_period(
        "POLICY-001",
        PERIOD_START,
        PERIOD_END,
    )

    assert row is not None
    assert row["shadow_entitlement_total"] == "3.50"
    assert row["crystallizable_amount"] == "3.50"
    assert Decimal(row["shadow_entitlement_total"]) != Decimal("15")
    assert Decimal(row["shadow_entitlement_total"]) != Decimal("17.5")
