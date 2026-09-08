from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from backend.commercialization.performance_accounting import (
    PerformanceAccountState,
    PerformanceAccountingTransition,
)
from backend.commercialization.performance_compensation import (
    PerformanceCompensationIneligibleError,
    PerformanceCompensationTerms,
    ShadowCompensationEntitlement,
    build_shadow_compensation_entitlement,
)


def _terms(
    *,
    rate: Decimal = Decimal("0.20"),
    currency: str = "CAD",
    accepted: bool = True,
    evidence_refs: tuple[str, ...] = ("agreement:TERMS-001",),
    terms_id: str = "TERMS-001",
    effective_from: str = "2026-01-01",
    effective_to: str | None = None,
) -> PerformanceCompensationTerms:
    return PerformanceCompensationTerms(
        terms_id=terms_id,
        currency=currency,
        performance_compensation_rate=rate,
        effective_from=effective_from,
        evidence_refs=evidence_refs,
        accepted=accepted,
        effective_to=effective_to,
    )


def _transition(
    *,
    trade_id: str = "TRADE-001",
    currency: str = "CAD",
    attributable_realized_pnl: Decimal = Decimal("5"),
    recovered_loss: Decimal = Decimal("0"),
    new_economic_gain: Decimal = Decimal("5"),
    previous_cumulative: Decimal = Decimal("100"),
    previous_hwm: Decimal = Decimal("100"),
    new_cumulative: Decimal = Decimal("105"),
    new_hwm: Decimal = Decimal("105"),
) -> PerformanceAccountingTransition:
    previous_state = PerformanceAccountState(
        currency=currency,
        cumulative_attributable_pnl=previous_cumulative,
        high_water_mark=previous_hwm,
        loss_carryforward=max(
            previous_hwm - previous_cumulative,
            Decimal("0"),
        ),
    )
    new_state = PerformanceAccountState(
        currency=currency,
        cumulative_attributable_pnl=new_cumulative,
        high_water_mark=new_hwm,
        loss_carryforward=max(
            new_hwm - new_cumulative,
            Decimal("0"),
        ),
    )
    return PerformanceAccountingTransition(
        trade_id=trade_id,
        previous_state=previous_state,
        new_state=new_state,
        attributable_realized_pnl=attributable_realized_pnl,
        recovered_loss=recovered_loss,
        new_economic_gain=new_economic_gain,
    )


def test_valid_entitlement_from_positive_new_economic_gain():
    entitlement = build_shadow_compensation_entitlement(
        _transition(
            attributable_realized_pnl=Decimal("100"),
            recovered_loss=Decimal("0"),
            new_economic_gain=Decimal("100"),
            previous_cumulative=Decimal("0"),
            previous_hwm=Decimal("0"),
            new_cumulative=Decimal("100"),
            new_hwm=Decimal("100"),
        ),
        _terms(rate=Decimal("0.20")),
        "2026-09-08T19:00:00Z",
    )

    assert entitlement.shadow_compensation_amount == Decimal("20")
    assert entitlement.new_economic_gain == Decimal("100")
    assert entitlement.compensation_rate == Decimal("0.20")
    assert entitlement.currency == "CAD"
    assert entitlement.terms_id == "TERMS-001"
    assert entitlement.trade_id == "TRADE-001"


def test_zero_gain_yields_zero_shadow_entitlement():
    entitlement = build_shadow_compensation_entitlement(
        _transition(
            attributable_realized_pnl=Decimal("20"),
            recovered_loss=Decimal("20"),
            new_economic_gain=Decimal("0"),
            previous_cumulative=Decimal("80"),
            previous_hwm=Decimal("100"),
            new_cumulative=Decimal("100"),
            new_hwm=Decimal("100"),
        ),
        _terms(rate=Decimal("0.20")),
        "2026-09-08T19:00:00Z",
    )

    assert entitlement.new_economic_gain == Decimal("0")
    assert entitlement.shadow_compensation_amount == Decimal("0")


def test_recovered_loss_is_excluded_from_compensation_base():
    transition = _transition(
        attributable_realized_pnl=Decimal("15"),
        recovered_loss=Decimal("10"),
        new_economic_gain=Decimal("5"),
        previous_cumulative=Decimal("90"),
        previous_hwm=Decimal("100"),
        new_cumulative=Decimal("105"),
        new_hwm=Decimal("105"),
    )
    entitlement = build_shadow_compensation_entitlement(
        transition,
        _terms(rate=Decimal("0.20")),
        "2026-09-08T19:00:00Z",
    )

    assert transition.recovered_loss == Decimal("10")
    assert entitlement.new_economic_gain == Decimal("5")
    assert entitlement.shadow_compensation_amount == Decimal("1")
    assert entitlement.shadow_compensation_amount != Decimal("3")
    assert (
        entitlement.shadow_compensation_amount
        != transition.attributable_realized_pnl
        * Decimal("0.20")
    )


def test_currency_mismatch_fails_closed():
    with pytest.raises(
        PerformanceCompensationIneligibleError,
        match="currency does not match",
    ):
        build_shadow_compensation_entitlement(
            _transition(currency="CAD"),
            _terms(currency="USD"),
            "2026-09-08T19:00:00Z",
        )


def test_invalid_rate_below_zero_is_rejected():
    with pytest.raises(
        ValueError,
        match="cannot be negative",
    ):
        _terms(rate=Decimal("-0.01"))


def test_invalid_rate_above_one_is_rejected():
    with pytest.raises(
        ValueError,
        match="cannot exceed 1",
    ):
        _terms(rate=Decimal("1.01"))


def test_float_rate_is_rejected():
    with pytest.raises(TypeError, match="must be Decimal"):
        _terms(rate=0.20)  # type: ignore[arg-type]


def test_non_finite_rate_is_rejected():
    with pytest.raises(ValueError, match="must be finite"):
        _terms(rate=Decimal("Infinity"))


def test_unaccepted_terms_are_rejected():
    with pytest.raises(
        PerformanceCompensationIneligibleError,
        match="not accepted",
    ):
        build_shadow_compensation_entitlement(
            _transition(),
            _terms(accepted=False),
            "2026-09-08T19:00:00Z",
        )


def test_missing_evidence_is_rejected():
    with pytest.raises(
        ValueError,
        match="require evidence",
    ):
        _terms(evidence_refs=())


def test_terms_object_is_immutable():
    terms = _terms()

    with pytest.raises(FrozenInstanceError):
        terms.accepted = False


def test_entitlement_object_is_immutable():
    entitlement = build_shadow_compensation_entitlement(
        _transition(),
        _terms(),
        "2026-09-08T19:00:00Z",
    )

    with pytest.raises(FrozenInstanceError):
        entitlement.shadow_compensation_amount = Decimal("999")


def test_no_fee_collection_authority():
    terms = _terms()
    entitlement = build_shadow_compensation_entitlement(
        _transition(),
        terms,
        "2026-09-08T19:00:00Z",
    )

    assert terms.real_fee_collection_allowed is False
    assert entitlement.real_fee_collection_allowed is False


def test_no_client_funds_deduction_authority():
    terms = _terms()
    entitlement = build_shadow_compensation_entitlement(
        _transition(),
        terms,
        "2026-09-08T19:00:00Z",
    )

    assert terms.client_funds_deduction_allowed is False
    assert entitlement.client_funds_deduction_allowed is False


def test_no_automatic_debit_authority():
    terms = _terms()
    entitlement = build_shadow_compensation_entitlement(
        _transition(),
        terms,
        "2026-09-08T19:00:00Z",
    )

    assert terms.automatic_debit_allowed is False
    assert entitlement.automatic_debit_allowed is False


def test_no_invoice_settlement_authority():
    terms = _terms()
    entitlement = build_shadow_compensation_entitlement(
        _transition(),
        terms,
        "2026-09-08T19:00:00Z",
    )

    assert terms.invoice_settlement_allowed is False
    assert entitlement.invoice_settlement_allowed is False


def test_no_execution_authority():
    terms = _terms()
    entitlement = build_shadow_compensation_entitlement(
        _transition(),
        terms,
        "2026-09-08T19:00:00Z",
    )

    assert terms.execution_authority is False
    assert entitlement.execution_authority is False
