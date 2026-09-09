from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from backend.commercialization.billable_obligation import (
    BillableObligationIneligibleError,
    BillableObligationStatus,
    CommercialBillableObligation,
    build_billable_obligation,
)
from backend.commercialization.settlement_readiness import (
    CommercialSettlementReadiness,
    SettlementReadinessStatus,
)


PERIOD_START = "2026-03-01T00:00:00+00:00"
PERIOD_END = "2026-04-01T00:00:00+00:00"
READINESS_AT = "2026-04-02T09:00:00+00:00"
RECOGNIZED_AT = "2026-04-03T10:00:00+00:00"


def _readiness(
    *,
    status: SettlementReadinessStatus = SettlementReadinessStatus.READY,
    crystallizable_amount: Decimal = Decimal("1"),
    policy_id: str = "POLICY-001",
    terms_id: str = "TERMS-001",
    currency: str = "CAD",
) -> CommercialSettlementReadiness:
    return CommercialSettlementReadiness(
        policy_id=policy_id,
        terms_id=terms_id,
        currency=currency,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        crystallizable_amount=crystallizable_amount,
        assessed_at=READINESS_AT,
        status=status,
        evidence_refs=("readiness:OPS-1",),
    )


def test_valid_billable_from_ready():
    obligation = build_billable_obligation(
        _readiness(
            status=SettlementReadinessStatus.READY,
            crystallizable_amount=Decimal("1"),
        ),
        BillableObligationStatus.BILLABLE,
        RECOGNIZED_AT,
        ("billable:OPS-1",),
    )

    assert obligation.status is BillableObligationStatus.BILLABLE
    assert obligation.policy_id == "POLICY-001"
    assert obligation.terms_id == "TERMS-001"
    assert obligation.currency == "CAD"
    assert obligation.period_start == PERIOD_START
    assert obligation.period_end == PERIOD_END
    assert obligation.billable_amount == Decimal("1")


def test_valid_not_billable():
    obligation = build_billable_obligation(
        _readiness(),
        BillableObligationStatus.NOT_BILLABLE,
        RECOGNIZED_AT,
        ("billable:OPS-1",),
    )

    assert obligation.status is BillableObligationStatus.NOT_BILLABLE


def test_valid_blocked():
    obligation = build_billable_obligation(
        _readiness(),
        BillableObligationStatus.BLOCKED,
        RECOGNIZED_AT,
        ("billable:OPS-1",),
    )

    assert obligation.status is BillableObligationStatus.BLOCKED


def test_valid_expired():
    obligation = build_billable_obligation(
        _readiness(),
        BillableObligationStatus.EXPIRED,
        RECOGNIZED_AT,
        ("billable:OPS-1",),
    )

    assert obligation.status is BillableObligationStatus.EXPIRED


@pytest.mark.parametrize(
    "upstream_status",
    [
        SettlementReadinessStatus.NOT_READY,
        SettlementReadinessStatus.PENDING_APPROVAL,
        SettlementReadinessStatus.BLOCKED,
        SettlementReadinessStatus.EXPIRED,
    ],
)
def test_billable_rejected_for_non_ready_upstream(upstream_status):
    with pytest.raises(
        BillableObligationIneligibleError,
        match="BILLABLE requires READY",
    ):
        build_billable_obligation(
            _readiness(status=upstream_status),
            BillableObligationStatus.BILLABLE,
            RECOGNIZED_AT,
            ("billable:OPS-1",),
        )


def test_zero_amount_billable_supported_when_upstream_ready():
    obligation = build_billable_obligation(
        _readiness(
            status=SettlementReadinessStatus.READY,
            crystallizable_amount=Decimal("0"),
        ),
        BillableObligationStatus.BILLABLE,
        RECOGNIZED_AT,
        ("billable:OPS-1",),
    )

    assert obligation.status is BillableObligationStatus.BILLABLE
    assert obligation.billable_amount == Decimal("0")
    assert obligation.invoice_creation_allowed is False
    assert obligation.receivable_recognition_allowed is False


def test_billable_amount_copied_exactly():
    readiness = _readiness(crystallizable_amount=Decimal("3.50"))
    obligation = build_billable_obligation(
        readiness,
        BillableObligationStatus.BILLABLE,
        RECOGNIZED_AT,
        ("billable:OPS-1",),
    )

    assert obligation.billable_amount == Decimal("3.50")
    assert obligation.billable_amount == readiness.crystallizable_amount


def test_decimal_representation_preserved():
    readiness = _readiness(crystallizable_amount=Decimal("1.00"))
    obligation = build_billable_obligation(
        readiness,
        BillableObligationStatus.BILLABLE,
        RECOGNIZED_AT,
        ("billable:OPS-1",),
    )

    assert str(obligation.billable_amount) == "1.00"


def test_no_economic_recalculation_from_upstream_trade_chain():
    # Upstream semantic chain: gain 15 / recovered 10 / new gain 5 /
    # rate 0.20 => shadow/crystallized/readiness amount 1, not 3/5/15.
    obligation = build_billable_obligation(
        _readiness(crystallizable_amount=Decimal("1")),
        BillableObligationStatus.BILLABLE,
        RECOGNIZED_AT,
        ("billable:OPS-1",),
    )

    assert obligation.billable_amount == Decimal("1")
    assert obligation.billable_amount != Decimal("3")
    assert obligation.billable_amount != Decimal("5")
    assert obligation.billable_amount != Decimal("15")
    assert obligation.invoice_creation_allowed is False
    assert obligation.receivable_recognition_allowed is False
    assert obligation.ledger_posting_allowed is False
    assert obligation.payment_initiation_allowed is False
    assert obligation.money_movement_allowed is False


def test_invalid_blank_policy_id_rejected_on_direct_construction():
    with pytest.raises(ValueError, match="policy_id"):
        CommercialBillableObligation(
            policy_id=" ",
            terms_id="TERMS-001",
            currency="CAD",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            billable_amount=Decimal("1"),
            recognized_at=RECOGNIZED_AT,
            status=BillableObligationStatus.NOT_BILLABLE,
            evidence_refs=("billable:OPS-1",),
        )


def test_invalid_blank_terms_id_rejected():
    with pytest.raises(ValueError, match="terms_id"):
        CommercialBillableObligation(
            policy_id="POLICY-001",
            terms_id="",
            currency="CAD",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            billable_amount=Decimal("1"),
            recognized_at=RECOGNIZED_AT,
            status=BillableObligationStatus.NOT_BILLABLE,
            evidence_refs=("billable:OPS-1",),
        )


def test_lowercase_currency_rejected():
    with pytest.raises(ValueError, match="currency"):
        CommercialBillableObligation(
            policy_id="POLICY-001",
            terms_id="TERMS-001",
            currency="cad",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            billable_amount=Decimal("1"),
            recognized_at=RECOGNIZED_AT,
            status=BillableObligationStatus.NOT_BILLABLE,
            evidence_refs=("billable:OPS-1",),
        )


def test_non_decimal_amount_rejected():
    with pytest.raises(TypeError, match="must be Decimal"):
        CommercialBillableObligation(
            policy_id="POLICY-001",
            terms_id="TERMS-001",
            currency="CAD",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            billable_amount=1.0,  # type: ignore[arg-type]
            recognized_at=RECOGNIZED_AT,
            status=BillableObligationStatus.NOT_BILLABLE,
            evidence_refs=("billable:OPS-1",),
        )


def test_non_finite_decimal_rejected():
    with pytest.raises(ValueError, match="must be finite"):
        CommercialBillableObligation(
            policy_id="POLICY-001",
            terms_id="TERMS-001",
            currency="CAD",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            billable_amount=Decimal("Infinity"),
            recognized_at=RECOGNIZED_AT,
            status=BillableObligationStatus.NOT_BILLABLE,
            evidence_refs=("billable:OPS-1",),
        )


def test_negative_amount_rejected():
    with pytest.raises(ValueError, match="cannot be negative"):
        CommercialBillableObligation(
            policy_id="POLICY-001",
            terms_id="TERMS-001",
            currency="CAD",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            billable_amount=Decimal("-0.01"),
            recognized_at=RECOGNIZED_AT,
            status=BillableObligationStatus.NOT_BILLABLE,
            evidence_refs=("billable:OPS-1",),
        )


def test_naive_recognized_at_rejected():
    with pytest.raises(ValueError, match="timezone-aware UTC"):
        build_billable_obligation(
            _readiness(),
            BillableObligationStatus.NOT_BILLABLE,
            "2026-04-03T10:00:00",
            ("billable:OPS-1",),
        )


def test_non_utc_recognized_at_rejected():
    with pytest.raises(ValueError, match="UTC"):
        build_billable_obligation(
            _readiness(),
            BillableObligationStatus.NOT_BILLABLE,
            "2026-04-03T10:00:00-04:00",
            ("billable:OPS-1",),
        )


def test_invalid_period_ordering_rejected():
    with pytest.raises(ValueError, match="period_end must be after"):
        CommercialBillableObligation(
            policy_id="POLICY-001",
            terms_id="TERMS-001",
            currency="CAD",
            period_start=PERIOD_START,
            period_end=PERIOD_START,
            billable_amount=Decimal("1"),
            recognized_at=RECOGNIZED_AT,
            status=BillableObligationStatus.NOT_BILLABLE,
            evidence_refs=("billable:OPS-1",),
        )


def test_missing_evidence_rejected():
    with pytest.raises(ValueError, match="evidence_refs"):
        build_billable_obligation(
            _readiness(),
            BillableObligationStatus.NOT_BILLABLE,
            RECOGNIZED_AT,
            (),
        )


def test_blank_evidence_ref_rejected():
    with pytest.raises(ValueError, match="evidence refs"):
        build_billable_obligation(
            _readiness(),
            BillableObligationStatus.NOT_BILLABLE,
            RECOGNIZED_AT,
            (" ",),
        )


def test_invalid_status_type_rejected():
    with pytest.raises(TypeError, match="BillableObligationStatus"):
        build_billable_obligation(
            _readiness(),
            "BILLABLE",  # type: ignore[arg-type]
            RECOGNIZED_AT,
            ("billable:OPS-1",),
        )


def test_object_is_immutable():
    obligation = build_billable_obligation(
        _readiness(),
        BillableObligationStatus.BILLABLE,
        RECOGNIZED_AT,
        ("billable:OPS-1",),
    )

    with pytest.raises(FrozenInstanceError):
        obligation.status = BillableObligationStatus.BLOCKED


def test_no_invoice_creation_authority():
    obligation = build_billable_obligation(
        _readiness(),
        BillableObligationStatus.BILLABLE,
        RECOGNIZED_AT,
        ("billable:OPS-1",),
    )

    assert obligation.invoice_creation_allowed is False


def test_no_receivable_recognition_authority():
    obligation = build_billable_obligation(
        _readiness(),
        BillableObligationStatus.BILLABLE,
        RECOGNIZED_AT,
        ("billable:OPS-1",),
    )

    assert obligation.receivable_recognition_allowed is False


def test_no_ledger_posting_authority():
    obligation = build_billable_obligation(
        _readiness(),
        BillableObligationStatus.BILLABLE,
        RECOGNIZED_AT,
        ("billable:OPS-1",),
    )

    assert obligation.ledger_posting_allowed is False


def test_no_revenue_recognition_authority():
    obligation = build_billable_obligation(
        _readiness(),
        BillableObligationStatus.BILLABLE,
        RECOGNIZED_AT,
        ("billable:OPS-1",),
    )

    assert obligation.revenue_recognition_allowed is False


def test_no_tax_calculation_authority():
    obligation = build_billable_obligation(
        _readiness(),
        BillableObligationStatus.BILLABLE,
        RECOGNIZED_AT,
        ("billable:OPS-1",),
    )

    assert obligation.tax_calculation_allowed is False


def test_no_fee_collection_authority():
    obligation = build_billable_obligation(
        _readiness(),
        BillableObligationStatus.BILLABLE,
        RECOGNIZED_AT,
        ("billable:OPS-1",),
    )

    assert obligation.real_fee_collection_allowed is False


def test_no_client_funds_deduction_authority():
    obligation = build_billable_obligation(
        _readiness(),
        BillableObligationStatus.BILLABLE,
        RECOGNIZED_AT,
        ("billable:OPS-1",),
    )

    assert obligation.client_funds_deduction_allowed is False


def test_no_automatic_debit_authority():
    obligation = build_billable_obligation(
        _readiness(),
        BillableObligationStatus.BILLABLE,
        RECOGNIZED_AT,
        ("billable:OPS-1",),
    )

    assert obligation.automatic_debit_allowed is False


def test_no_invoice_settlement_authority():
    obligation = build_billable_obligation(
        _readiness(),
        BillableObligationStatus.BILLABLE,
        RECOGNIZED_AT,
        ("billable:OPS-1",),
    )

    assert obligation.invoice_settlement_allowed is False


def test_no_payment_initiation_authority():
    obligation = build_billable_obligation(
        _readiness(),
        BillableObligationStatus.BILLABLE,
        RECOGNIZED_AT,
        ("billable:OPS-1",),
    )

    assert obligation.payment_initiation_allowed is False


def test_no_money_movement_authority():
    obligation = build_billable_obligation(
        _readiness(),
        BillableObligationStatus.BILLABLE,
        RECOGNIZED_AT,
        ("billable:OPS-1",),
    )

    assert obligation.money_movement_allowed is False


def test_no_broker_withdrawal_authority():
    obligation = build_billable_obligation(
        _readiness(),
        BillableObligationStatus.BILLABLE,
        RECOGNIZED_AT,
        ("billable:OPS-1",),
    )

    assert obligation.broker_withdrawal_allowed is False


def test_no_execution_authority():
    obligation = build_billable_obligation(
        _readiness(),
        BillableObligationStatus.BILLABLE,
        RECOGNIZED_AT,
        ("billable:OPS-1",),
    )

    assert obligation.execution_authority is False
