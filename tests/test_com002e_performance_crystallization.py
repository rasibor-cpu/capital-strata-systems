from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from backend.commercialization.performance_compensation import (
    ShadowCompensationEntitlement,
)
from backend.commercialization.performance_crystallization import (
    CrystallizationAssessment,
    CrystallizationFrequency,
    CrystallizationStatus,
    PerformanceCompensationLifecyclePolicy,
    PerformanceCrystallizationIneligibleError,
    build_crystallization_assessment,
)


UTC_FROM = "2026-01-01T00:00:00+00:00"
UTC_TO = "2026-12-31T00:00:00+00:00"
PERIOD_START = "2026-03-01T00:00:00+00:00"
PERIOD_END = "2026-04-01T00:00:00+00:00"
ASSESSED_AT = "2026-04-01T12:00:00+00:00"


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


def _entitlement(
    *,
    trade_id: str = "TRADE-001",
    terms_id: str = "TERMS-001",
    currency: str = "CAD",
    new_economic_gain: Decimal = Decimal("5"),
    compensation_rate: Decimal = Decimal("0.20"),
    shadow_compensation_amount: Decimal = Decimal("1"),
) -> ShadowCompensationEntitlement:
    return ShadowCompensationEntitlement(
        trade_id=trade_id,
        terms_id=terms_id,
        currency=currency,
        new_economic_gain=new_economic_gain,
        compensation_rate=compensation_rate,
        shadow_compensation_amount=shadow_compensation_amount,
        calculation_timestamp="2026-03-15T10:00:00Z",
        evidence_refs=("agreement:TERMS-001",),
    )


def test_valid_lifecycle_policy():
    policy = _policy(crystallize_on_termination=True)

    assert policy.policy_id == "POLICY-001"
    assert policy.terms_id == "TERMS-001"
    assert policy.currency == "CAD"
    assert (
        policy.crystallization_frequency
        == CrystallizationFrequency.QUARTERLY
    )
    assert policy.crystallize_on_termination is True
    assert policy.effective_from == UTC_FROM
    assert policy.effective_to == UTC_TO


def test_invalid_blank_policy_id():
    with pytest.raises(ValueError, match="policy_id"):
        _policy(policy_id=" ")


def test_invalid_blank_terms_id():
    with pytest.raises(ValueError, match="terms_id"):
        _policy(terms_id="")


def test_lowercase_currency_rejected():
    with pytest.raises(ValueError, match="currency"):
        _policy(currency="cad")


def test_invalid_frequency_type_rejected():
    with pytest.raises(TypeError, match="CrystallizationFrequency"):
        _policy(frequency="MONTHLY")  # type: ignore[arg-type]


def test_naive_effective_from_rejected():
    with pytest.raises(ValueError, match="timezone-aware UTC"):
        _policy(effective_from="2026-01-01T00:00:00")


def test_non_utc_effective_from_rejected():
    with pytest.raises(ValueError, match="UTC"):
        _policy(effective_from="2026-01-01T00:00:00-04:00")


def test_invalid_effective_to_rejected():
    with pytest.raises(ValueError, match="timezone-aware UTC"):
        _policy(effective_to="2026-12-31")


def test_effective_to_before_effective_from_rejected():
    with pytest.raises(ValueError, match="must not precede"):
        _policy(
            effective_from="2026-06-01T00:00:00+00:00",
            effective_to="2026-01-01T00:00:00+00:00",
        )


def test_missing_evidence_rejected():
    with pytest.raises(ValueError, match="evidence_refs"):
        _policy(evidence_refs=())


def test_policy_is_immutable():
    policy = _policy()

    with pytest.raises(FrozenInstanceError):
        policy.crystallize_on_termination = True


def test_eligible_assessment_sums_multiple_shadow_entitlements():
    assessment = build_crystallization_assessment(
        _policy(),
        (
            _entitlement(
                trade_id="TRADE-001",
                shadow_compensation_amount=Decimal("1.00"),
            ),
            _entitlement(
                trade_id="TRADE-002",
                new_economic_gain=Decimal("12.5"),
                shadow_compensation_amount=Decimal("2.50"),
            ),
        ),
        PERIOD_START,
        PERIOD_END,
        ASSESSED_AT,
        CrystallizationStatus.ELIGIBLE,
        ("assessment:Q1",),
    )

    assert assessment.shadow_entitlement_total == Decimal("3.50")
    assert assessment.crystallizable_amount == Decimal("3.50")
    assert assessment.status == CrystallizationStatus.ELIGIBLE


def test_not_due_gives_zero_crystallizable_amount():
    assessment = build_crystallization_assessment(
        _policy(),
        (_entitlement(shadow_compensation_amount=Decimal("1")),),
        PERIOD_START,
        PERIOD_END,
        ASSESSED_AT,
        CrystallizationStatus.NOT_DUE,
        ("assessment:Q1",),
    )

    assert assessment.shadow_entitlement_total == Decimal("1")
    assert assessment.crystallizable_amount == Decimal("0")


def test_blocked_gives_zero_crystallizable_amount():
    assessment = build_crystallization_assessment(
        _policy(),
        (_entitlement(shadow_compensation_amount=Decimal("1")),),
        PERIOD_START,
        PERIOD_END,
        ASSESSED_AT,
        CrystallizationStatus.BLOCKED,
        ("assessment:Q1",),
    )

    assert assessment.crystallizable_amount == Decimal("0")


def test_expired_gives_zero_crystallizable_amount():
    assessment = build_crystallization_assessment(
        _policy(),
        (_entitlement(shadow_compensation_amount=Decimal("1")),),
        PERIOD_START,
        PERIOD_END,
        ASSESSED_AT,
        CrystallizationStatus.EXPIRED,
        ("assessment:Q1",),
    )

    assert assessment.crystallizable_amount == Decimal("0")


def test_eligible_empty_period_gives_zero():
    assessment = build_crystallization_assessment(
        _policy(),
        (),
        PERIOD_START,
        PERIOD_END,
        ASSESSED_AT,
        CrystallizationStatus.ELIGIBLE,
        ("assessment:Q1",),
    )

    assert assessment.shadow_entitlement_total == Decimal("0")
    assert assessment.crystallizable_amount == Decimal("0")


def test_terms_mismatch_fails_closed():
    with pytest.raises(
        PerformanceCrystallizationIneligibleError,
        match="terms_id",
    ):
        build_crystallization_assessment(
            _policy(terms_id="TERMS-001"),
            (_entitlement(terms_id="TERMS-OTHER"),),
            PERIOD_START,
            PERIOD_END,
            ASSESSED_AT,
            CrystallizationStatus.ELIGIBLE,
            ("assessment:Q1",),
        )


def test_currency_mismatch_fails_closed():
    with pytest.raises(
        PerformanceCrystallizationIneligibleError,
        match="currency",
    ):
        build_crystallization_assessment(
            _policy(currency="CAD"),
            (_entitlement(currency="USD"),),
            PERIOD_START,
            PERIOD_END,
            ASSESSED_AT,
            CrystallizationStatus.ELIGIBLE,
            ("assessment:Q1",),
        )


def test_duplicate_trade_id_fails_closed():
    with pytest.raises(
        PerformanceCrystallizationIneligibleError,
        match="duplicate",
    ):
        build_crystallization_assessment(
            _policy(),
            (
                _entitlement(trade_id="TRADE-001"),
                _entitlement(
                    trade_id="TRADE-001",
                    shadow_compensation_amount=Decimal("2"),
                ),
            ),
            PERIOD_START,
            PERIOD_END,
            ASSESSED_AT,
            CrystallizationStatus.ELIGIBLE,
            ("assessment:Q1",),
        )


def test_negative_entitlement_amount_fails_closed():
    with pytest.raises(ValueError, match="cannot be negative"):
        _entitlement(shadow_compensation_amount=Decimal("-1"))


def test_non_decimal_amount_fails_closed():
    with pytest.raises(TypeError, match="must be Decimal"):
        ShadowCompensationEntitlement(
            trade_id="TRADE-001",
            terms_id="TERMS-001",
            currency="CAD",
            new_economic_gain=Decimal("5"),
            compensation_rate=Decimal("0.20"),
            shadow_compensation_amount=1.0,  # type: ignore[arg-type]
            calculation_timestamp="2026-03-15T10:00:00Z",
            evidence_refs=("agreement:TERMS-001",),
        )


def test_non_finite_amount_fails_closed():
    with pytest.raises(ValueError, match="must be finite"):
        ShadowCompensationEntitlement(
            trade_id="TRADE-001",
            terms_id="TERMS-001",
            currency="CAD",
            new_economic_gain=Decimal("5"),
            compensation_rate=Decimal("0.20"),
            shadow_compensation_amount=Decimal("Infinity"),
            calculation_timestamp="2026-03-15T10:00:00Z",
            evidence_refs=("agreement:TERMS-001",),
        )


def test_period_end_not_after_period_start_rejected():
    with pytest.raises(ValueError, match="period_end must be after"):
        build_crystallization_assessment(
            _policy(),
            (),
            PERIOD_START,
            PERIOD_START,
            ASSESSED_AT,
            CrystallizationStatus.ELIGIBLE,
            ("assessment:Q1",),
        )


def test_assessment_outside_policy_effective_window_rejected():
    with pytest.raises(
        PerformanceCrystallizationIneligibleError,
        match="outside policy effective window",
    ):
        build_crystallization_assessment(
            _policy(
                effective_from="2026-06-01T00:00:00+00:00",
                effective_to="2026-12-31T00:00:00+00:00",
            ),
            (),
            PERIOD_START,
            PERIOD_END,
            ASSESSED_AT,
            CrystallizationStatus.ELIGIBLE,
            ("assessment:Q1",),
        )


def test_exact_decimal_arithmetic_preserved():
    assessment = build_crystallization_assessment(
        _policy(),
        (
            _entitlement(
                trade_id="TRADE-001",
                shadow_compensation_amount=Decimal("0.1"),
            ),
            _entitlement(
                trade_id="TRADE-002",
                new_economic_gain=Decimal("1"),
                shadow_compensation_amount=Decimal("0.2"),
            ),
        ),
        PERIOD_START,
        PERIOD_END,
        ASSESSED_AT,
        CrystallizationStatus.ELIGIBLE,
        ("assessment:Q1",),
    )

    assert assessment.shadow_entitlement_total == Decimal("0.3")
    assert assessment.crystallizable_amount == Decimal("0.3")


def test_aggregation_uses_only_shadow_compensation_amount():
    entitlement = _entitlement(
        new_economic_gain=Decimal("5"),
        compensation_rate=Decimal("0.20"),
        shadow_compensation_amount=Decimal("1"),
    )

    assessment = build_crystallization_assessment(
        _policy(),
        (entitlement,),
        PERIOD_START,
        PERIOD_END,
        ASSESSED_AT,
        CrystallizationStatus.ELIGIBLE,
        ("assessment:Q1",),
    )

    assert entitlement.new_economic_gain == Decimal("5")
    assert assessment.shadow_entitlement_total == Decimal("1")
    assert assessment.crystallizable_amount == Decimal("1")
    assert assessment.shadow_entitlement_total != Decimal("3")
    assert assessment.shadow_entitlement_total != Decimal("5")
    assert assessment.shadow_entitlement_total != Decimal("15")


def test_assessment_is_immutable():
    assessment = build_crystallization_assessment(
        _policy(),
        (),
        PERIOD_START,
        PERIOD_END,
        ASSESSED_AT,
        CrystallizationStatus.ELIGIBLE,
        ("assessment:Q1",),
    )

    with pytest.raises(FrozenInstanceError):
        assessment.crystallizable_amount = Decimal("999")


def test_no_fee_collection_authority():
    policy = _policy()
    assessment = build_crystallization_assessment(
        policy,
        (),
        PERIOD_START,
        PERIOD_END,
        ASSESSED_AT,
        CrystallizationStatus.ELIGIBLE,
        ("assessment:Q1",),
    )

    assert policy.real_fee_collection_allowed is False
    assert assessment.real_fee_collection_allowed is False


def test_no_client_funds_deduction_authority():
    policy = _policy()
    assessment = build_crystallization_assessment(
        policy,
        (),
        PERIOD_START,
        PERIOD_END,
        ASSESSED_AT,
        CrystallizationStatus.ELIGIBLE,
        ("assessment:Q1",),
    )

    assert policy.client_funds_deduction_allowed is False
    assert assessment.client_funds_deduction_allowed is False


def test_no_automatic_debit_authority():
    policy = _policy()
    assessment = build_crystallization_assessment(
        policy,
        (),
        PERIOD_START,
        PERIOD_END,
        ASSESSED_AT,
        CrystallizationStatus.ELIGIBLE,
        ("assessment:Q1",),
    )

    assert policy.automatic_debit_allowed is False
    assert assessment.automatic_debit_allowed is False


def test_no_invoice_settlement_authority():
    policy = _policy()
    assessment = build_crystallization_assessment(
        policy,
        (),
        PERIOD_START,
        PERIOD_END,
        ASSESSED_AT,
        CrystallizationStatus.ELIGIBLE,
        ("assessment:Q1",),
    )

    assert policy.invoice_settlement_allowed is False
    assert assessment.invoice_settlement_allowed is False


def test_no_money_movement_authority():
    policy = _policy()
    assessment = build_crystallization_assessment(
        policy,
        (),
        PERIOD_START,
        PERIOD_END,
        ASSESSED_AT,
        CrystallizationStatus.ELIGIBLE,
        ("assessment:Q1",),
    )

    assert policy.money_movement_allowed is False
    assert assessment.money_movement_allowed is False


def test_no_execution_authority():
    policy = _policy()
    assessment = build_crystallization_assessment(
        policy,
        (),
        PERIOD_START,
        PERIOD_END,
        ASSESSED_AT,
        CrystallizationStatus.ELIGIBLE,
        ("assessment:Q1",),
    )

    assert policy.execution_authority is False
    assert assessment.execution_authority is False


def test_assessment_direct_construction_validates_status_type():
    with pytest.raises(TypeError, match="CrystallizationStatus"):
        CrystallizationAssessment(
            policy_id="POLICY-001",
            terms_id="TERMS-001",
            currency="CAD",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            assessed_at=ASSESSED_AT,
            shadow_entitlement_total=Decimal("0"),
            crystallizable_amount=Decimal("0"),
            status="ELIGIBLE",  # type: ignore[arg-type]
            evidence_refs=("assessment:Q1",),
        )
