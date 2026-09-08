from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from backend.commercialization.performance_crystallization import (
    CrystallizationAssessment,
    CrystallizationStatus,
)
from backend.commercialization.settlement_readiness import (
    CommercialSettlementReadiness,
    SettlementReadinessIneligibleError,
    SettlementReadinessStatus,
    build_settlement_readiness,
)


PERIOD_START = "2026-03-01T00:00:00+00:00"
PERIOD_END = "2026-04-01T00:00:00+00:00"
ASSESSED_AT = "2026-04-01T12:00:00+00:00"
READINESS_AT = "2026-04-02T09:00:00+00:00"


def _assessment(
    *,
    status: CrystallizationStatus = CrystallizationStatus.ELIGIBLE,
    crystallizable_amount: Decimal = Decimal("1"),
    shadow_entitlement_total: Decimal | None = None,
    policy_id: str = "POLICY-001",
    terms_id: str = "TERMS-001",
    currency: str = "CAD",
) -> CrystallizationAssessment:
    if shadow_entitlement_total is None:
        shadow_entitlement_total = crystallizable_amount
        if status != CrystallizationStatus.ELIGIBLE:
            shadow_entitlement_total = max(
                crystallizable_amount,
                Decimal("1"),
            )
            crystallizable_amount = Decimal("0")

    return CrystallizationAssessment(
        policy_id=policy_id,
        terms_id=terms_id,
        currency=currency,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        assessed_at=ASSESSED_AT,
        shadow_entitlement_total=shadow_entitlement_total,
        crystallizable_amount=crystallizable_amount,
        status=status,
        evidence_refs=("assessment:Q1",),
    )


def test_valid_ready_from_eligible_crystallization_assessment():
    readiness = build_settlement_readiness(
        _assessment(
            status=CrystallizationStatus.ELIGIBLE,
            crystallizable_amount=Decimal("1"),
        ),
        SettlementReadinessStatus.READY,
        READINESS_AT,
        ("readiness:OPS-1",),
    )

    assert readiness.status is SettlementReadinessStatus.READY
    assert readiness.policy_id == "POLICY-001"
    assert readiness.terms_id == "TERMS-001"
    assert readiness.currency == "CAD"
    assert readiness.period_start == PERIOD_START
    assert readiness.period_end == PERIOD_END
    assert readiness.crystallizable_amount == Decimal("1")


def test_valid_not_ready():
    readiness = build_settlement_readiness(
        _assessment(),
        SettlementReadinessStatus.NOT_READY,
        READINESS_AT,
        ("readiness:OPS-1",),
    )

    assert readiness.status is SettlementReadinessStatus.NOT_READY


def test_valid_pending_approval():
    readiness = build_settlement_readiness(
        _assessment(),
        SettlementReadinessStatus.PENDING_APPROVAL,
        READINESS_AT,
        ("readiness:OPS-1",),
    )

    assert readiness.status is SettlementReadinessStatus.PENDING_APPROVAL


def test_valid_blocked():
    readiness = build_settlement_readiness(
        _assessment(),
        SettlementReadinessStatus.BLOCKED,
        READINESS_AT,
        ("readiness:OPS-1",),
    )

    assert readiness.status is SettlementReadinessStatus.BLOCKED


def test_valid_expired_readiness_status():
    readiness = build_settlement_readiness(
        _assessment(),
        SettlementReadinessStatus.EXPIRED,
        READINESS_AT,
        ("readiness:OPS-1",),
    )

    assert readiness.status is SettlementReadinessStatus.EXPIRED


@pytest.mark.parametrize(
    "upstream_status",
    [
        CrystallizationStatus.NOT_DUE,
        CrystallizationStatus.BLOCKED,
        CrystallizationStatus.EXPIRED,
    ],
)
def test_ready_rejected_for_non_eligible_upstream(upstream_status):
    with pytest.raises(
        SettlementReadinessIneligibleError,
        match="READY requires ELIGIBLE",
    ):
        build_settlement_readiness(
            _assessment(
                status=upstream_status,
                shadow_entitlement_total=Decimal("3.50"),
                crystallizable_amount=Decimal("0"),
            ),
            SettlementReadinessStatus.READY,
            READINESS_AT,
            ("readiness:OPS-1",),
        )


def test_ready_allowed_for_eligible_zero_crystallizable_amount():
    readiness = build_settlement_readiness(
        _assessment(
            status=CrystallizationStatus.ELIGIBLE,
            crystallizable_amount=Decimal("0"),
            shadow_entitlement_total=Decimal("0"),
        ),
        SettlementReadinessStatus.READY,
        READINESS_AT,
        ("readiness:OPS-1",),
    )

    assert readiness.status is SettlementReadinessStatus.READY
    assert readiness.crystallizable_amount == Decimal("0")
    assert readiness.real_fee_collection_allowed is False


def test_crystallizable_amount_copied_exactly_from_assessment():
    assessment = _assessment(
        crystallizable_amount=Decimal("3.50"),
        shadow_entitlement_total=Decimal("3.50"),
    )
    readiness = build_settlement_readiness(
        assessment,
        SettlementReadinessStatus.READY,
        READINESS_AT,
        ("readiness:OPS-1",),
    )

    assert readiness.crystallizable_amount == Decimal("3.50")
    assert readiness.crystallizable_amount is (
        assessment.crystallizable_amount
    ) or readiness.crystallizable_amount == (
        assessment.crystallizable_amount
    )


def test_decimal_representation_preserved():
    assessment = _assessment(
        crystallizable_amount=Decimal("1.00"),
        shadow_entitlement_total=Decimal("1.00"),
    )
    readiness = build_settlement_readiness(
        assessment,
        SettlementReadinessStatus.READY,
        READINESS_AT,
        ("readiness:OPS-1",),
    )

    assert str(readiness.crystallizable_amount) == "1.00"


def test_no_recalculation_from_upstream_trade_economics():
    # Upstream semantic chain: gain 15 / recovered 10 / new gain 5 /
    # rate 0.20 => shadow/crystallized amount 1, not 3/5/15.
    readiness = build_settlement_readiness(
        _assessment(crystallizable_amount=Decimal("1")),
        SettlementReadinessStatus.READY,
        READINESS_AT,
        ("readiness:OPS-1",),
    )

    assert readiness.crystallizable_amount == Decimal("1")
    assert readiness.crystallizable_amount != Decimal("3")
    assert readiness.crystallizable_amount != Decimal("5")
    assert readiness.crystallizable_amount != Decimal("15")


def test_invalid_blank_policy_id_rejected_on_direct_construction():
    with pytest.raises(ValueError, match="policy_id"):
        CommercialSettlementReadiness(
            policy_id=" ",
            terms_id="TERMS-001",
            currency="CAD",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            crystallizable_amount=Decimal("1"),
            assessed_at=READINESS_AT,
            status=SettlementReadinessStatus.NOT_READY,
            evidence_refs=("readiness:OPS-1",),
        )


def test_invalid_blank_terms_id_rejected():
    with pytest.raises(ValueError, match="terms_id"):
        CommercialSettlementReadiness(
            policy_id="POLICY-001",
            terms_id="",
            currency="CAD",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            crystallizable_amount=Decimal("1"),
            assessed_at=READINESS_AT,
            status=SettlementReadinessStatus.NOT_READY,
            evidence_refs=("readiness:OPS-1",),
        )


def test_lowercase_currency_rejected():
    with pytest.raises(ValueError, match="currency"):
        CommercialSettlementReadiness(
            policy_id="POLICY-001",
            terms_id="TERMS-001",
            currency="cad",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            crystallizable_amount=Decimal("1"),
            assessed_at=READINESS_AT,
            status=SettlementReadinessStatus.NOT_READY,
            evidence_refs=("readiness:OPS-1",),
        )


def test_non_decimal_amount_rejected():
    with pytest.raises(TypeError, match="must be Decimal"):
        CommercialSettlementReadiness(
            policy_id="POLICY-001",
            terms_id="TERMS-001",
            currency="CAD",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            crystallizable_amount=1.0,  # type: ignore[arg-type]
            assessed_at=READINESS_AT,
            status=SettlementReadinessStatus.NOT_READY,
            evidence_refs=("readiness:OPS-1",),
        )


def test_non_finite_decimal_rejected():
    with pytest.raises(ValueError, match="must be finite"):
        CommercialSettlementReadiness(
            policy_id="POLICY-001",
            terms_id="TERMS-001",
            currency="CAD",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            crystallizable_amount=Decimal("Infinity"),
            assessed_at=READINESS_AT,
            status=SettlementReadinessStatus.NOT_READY,
            evidence_refs=("readiness:OPS-1",),
        )


def test_negative_amount_rejected():
    with pytest.raises(ValueError, match="cannot be negative"):
        CommercialSettlementReadiness(
            policy_id="POLICY-001",
            terms_id="TERMS-001",
            currency="CAD",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            crystallizable_amount=Decimal("-0.01"),
            assessed_at=READINESS_AT,
            status=SettlementReadinessStatus.NOT_READY,
            evidence_refs=("readiness:OPS-1",),
        )


def test_naive_assessed_at_rejected():
    with pytest.raises(ValueError, match="timezone-aware UTC"):
        build_settlement_readiness(
            _assessment(),
            SettlementReadinessStatus.NOT_READY,
            "2026-04-02T09:00:00",
            ("readiness:OPS-1",),
        )


def test_non_utc_assessed_at_rejected():
    with pytest.raises(ValueError, match="UTC"):
        build_settlement_readiness(
            _assessment(),
            SettlementReadinessStatus.NOT_READY,
            "2026-04-02T09:00:00-04:00",
            ("readiness:OPS-1",),
        )


def test_invalid_period_ordering_rejected():
    with pytest.raises(ValueError, match="period_end must be after"):
        CommercialSettlementReadiness(
            policy_id="POLICY-001",
            terms_id="TERMS-001",
            currency="CAD",
            period_start=PERIOD_START,
            period_end=PERIOD_START,
            crystallizable_amount=Decimal("1"),
            assessed_at=READINESS_AT,
            status=SettlementReadinessStatus.NOT_READY,
            evidence_refs=("readiness:OPS-1",),
        )


def test_missing_evidence_rejected():
    with pytest.raises(ValueError, match="evidence_refs"):
        build_settlement_readiness(
            _assessment(),
            SettlementReadinessStatus.NOT_READY,
            READINESS_AT,
            (),
        )


def test_blank_evidence_ref_rejected():
    with pytest.raises(ValueError, match="evidence refs"):
        build_settlement_readiness(
            _assessment(),
            SettlementReadinessStatus.NOT_READY,
            READINESS_AT,
            (" ",),
        )


def test_invalid_status_type_rejected():
    with pytest.raises(TypeError, match="SettlementReadinessStatus"):
        build_settlement_readiness(
            _assessment(),
            "READY",  # type: ignore[arg-type]
            READINESS_AT,
            ("readiness:OPS-1",),
        )


def test_readiness_object_is_immutable():
    readiness = build_settlement_readiness(
        _assessment(),
        SettlementReadinessStatus.READY,
        READINESS_AT,
        ("readiness:OPS-1",),
    )

    with pytest.raises(FrozenInstanceError):
        readiness.status = SettlementReadinessStatus.BLOCKED


def test_no_fee_collection_authority():
    readiness = build_settlement_readiness(
        _assessment(),
        SettlementReadinessStatus.READY,
        READINESS_AT,
        ("readiness:OPS-1",),
    )

    assert readiness.real_fee_collection_allowed is False


def test_no_client_funds_deduction_authority():
    readiness = build_settlement_readiness(
        _assessment(),
        SettlementReadinessStatus.READY,
        READINESS_AT,
        ("readiness:OPS-1",),
    )

    assert readiness.client_funds_deduction_allowed is False


def test_no_automatic_debit_authority():
    readiness = build_settlement_readiness(
        _assessment(),
        SettlementReadinessStatus.READY,
        READINESS_AT,
        ("readiness:OPS-1",),
    )

    assert readiness.automatic_debit_allowed is False


def test_no_invoice_settlement_authority():
    readiness = build_settlement_readiness(
        _assessment(),
        SettlementReadinessStatus.READY,
        READINESS_AT,
        ("readiness:OPS-1",),
    )

    assert readiness.invoice_settlement_allowed is False


def test_no_money_movement_authority():
    readiness = build_settlement_readiness(
        _assessment(),
        SettlementReadinessStatus.READY,
        READINESS_AT,
        ("readiness:OPS-1",),
    )

    assert readiness.money_movement_allowed is False


def test_no_broker_withdrawal_authority():
    readiness = build_settlement_readiness(
        _assessment(),
        SettlementReadinessStatus.READY,
        READINESS_AT,
        ("readiness:OPS-1",),
    )

    assert readiness.broker_withdrawal_allowed is False


def test_no_payment_initiation_authority():
    readiness = build_settlement_readiness(
        _assessment(),
        SettlementReadinessStatus.READY,
        READINESS_AT,
        ("readiness:OPS-1",),
    )

    assert readiness.payment_initiation_allowed is False


def test_no_execution_authority():
    readiness = build_settlement_readiness(
        _assessment(),
        SettlementReadinessStatus.READY,
        READINESS_AT,
        ("readiness:OPS-1",),
    )

    assert readiness.execution_authority is False
