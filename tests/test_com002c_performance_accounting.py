from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from backend.commercialization.performance_accounting import (
    PerformanceAccountState,
    apply_attributable_performance,
    initial_performance_account,
)
from backend.commercialization.performance_attribution import (
    AttributablePerformance,
)


def _performance(
    pnl: Decimal,
    trade_id: str = "TRADE-001",
    currency: str = "CAD",
) -> AttributablePerformance:
    return AttributablePerformance(
        trade_id=trade_id,
        advice_id="ADVICE-001",
        realized_pnl=pnl,
        currency=currency,
        verification_timestamp="2026-09-08T19:00:00Z",
        provenance_evidence_refs=(
            "trade-card:ADVICE-001",
        ),
        economics_evidence_refs=(
            "canonical-pnl:TRADE-001",
        ),
    )


def test_initial_account_starts_at_zero():
    state = initial_performance_account("CAD")

    assert state.cumulative_attributable_pnl == Decimal("0")
    assert state.high_water_mark == Decimal("0")
    assert state.loss_carryforward == Decimal("0")


def test_first_profit_sets_high_water_mark():
    state = initial_performance_account("CAD")

    result = apply_attributable_performance(
        state,
        _performance(Decimal("100")),
    )

    assert (
        result.new_state.cumulative_attributable_pnl
        == Decimal("100")
    )
    assert result.new_state.high_water_mark == Decimal("100")
    assert result.new_state.loss_carryforward == Decimal("0")
    assert result.recovered_loss == Decimal("0")
    assert result.new_economic_gain == Decimal("100")


def test_loss_below_high_water_mark_creates_carryforward():
    state = PerformanceAccountState(
        currency="CAD",
        cumulative_attributable_pnl=Decimal("100"),
        high_water_mark=Decimal("100"),
        loss_carryforward=Decimal("0"),
    )

    result = apply_attributable_performance(
        state,
        _performance(Decimal("-30")),
    )

    assert (
        result.new_state.cumulative_attributable_pnl
        == Decimal("70")
    )
    assert result.new_state.high_water_mark == Decimal("100")
    assert result.new_state.loss_carryforward == Decimal("30")
    assert result.recovered_loss == Decimal("0")
    assert result.new_economic_gain == Decimal("0")


def test_partial_recovery_reduces_loss_carryforward():
    state = PerformanceAccountState(
        currency="CAD",
        cumulative_attributable_pnl=Decimal("70"),
        high_water_mark=Decimal("100"),
        loss_carryforward=Decimal("30"),
    )

    result = apply_attributable_performance(
        state,
        _performance(Decimal("20")),
    )

    assert (
        result.new_state.cumulative_attributable_pnl
        == Decimal("90")
    )
    assert result.new_state.high_water_mark == Decimal("100")
    assert result.new_state.loss_carryforward == Decimal("10")
    assert result.recovered_loss == Decimal("20")
    assert result.new_economic_gain == Decimal("0")


def test_recovery_above_hwm_splits_recovery_and_new_gain():
    state = PerformanceAccountState(
        currency="CAD",
        cumulative_attributable_pnl=Decimal("90"),
        high_water_mark=Decimal("100"),
        loss_carryforward=Decimal("10"),
    )

    result = apply_attributable_performance(
        state,
        _performance(Decimal("15")),
    )

    assert (
        result.new_state.cumulative_attributable_pnl
        == Decimal("105")
    )
    assert result.new_state.high_water_mark == Decimal("105")
    assert result.new_state.loss_carryforward == Decimal("0")
    assert result.recovered_loss == Decimal("10")
    assert result.new_economic_gain == Decimal("5")


def test_additional_loss_increases_loss_carryforward():
    state = PerformanceAccountState(
        currency="CAD",
        cumulative_attributable_pnl=Decimal("70"),
        high_water_mark=Decimal("100"),
        loss_carryforward=Decimal("30"),
    )

    result = apply_attributable_performance(
        state,
        _performance(Decimal("-20")),
    )

    assert (
        result.new_state.cumulative_attributable_pnl
        == Decimal("50")
    )
    assert result.new_state.high_water_mark == Decimal("100")
    assert result.new_state.loss_carryforward == Decimal("50")
    assert result.new_economic_gain == Decimal("0")


def test_loss_can_drive_cumulative_performance_negative():
    state = initial_performance_account("CAD")

    result = apply_attributable_performance(
        state,
        _performance(Decimal("-25")),
    )

    assert (
        result.new_state.cumulative_attributable_pnl
        == Decimal("-25")
    )
    assert result.new_state.high_water_mark == Decimal("0")
    assert result.new_state.loss_carryforward == Decimal("25")


def test_zero_pnl_does_not_change_accounting_state():
    state = PerformanceAccountState(
        currency="CAD",
        cumulative_attributable_pnl=Decimal("80"),
        high_water_mark=Decimal("100"),
        loss_carryforward=Decimal("20"),
    )

    result = apply_attributable_performance(
        state,
        _performance(Decimal("0")),
    )

    assert result.new_state == state
    assert result.recovered_loss == Decimal("0")
    assert result.new_economic_gain == Decimal("0")


def test_currency_mismatch_fails_closed():
    state = initial_performance_account("CAD")

    with pytest.raises(
        ValueError,
        match="currency does not match",
    ):
        apply_attributable_performance(
            state,
            _performance(
                Decimal("10"),
                currency="USD",
            ),
        )


def test_inconsistent_loss_carryforward_is_rejected():
    with pytest.raises(
        ValueError,
        match="loss_carryforward must equal",
    ):
        PerformanceAccountState(
            currency="CAD",
            cumulative_attributable_pnl=Decimal("80"),
            high_water_mark=Decimal("100"),
            loss_carryforward=Decimal("5"),
        )


def test_accounting_state_is_immutable():
    state = initial_performance_account("CAD")

    with pytest.raises(FrozenInstanceError):
        state.high_water_mark = Decimal("999")


def test_transition_is_immutable():
    result = apply_attributable_performance(
        initial_performance_account("CAD"),
        _performance(Decimal("10")),
    )

    with pytest.raises(FrozenInstanceError):
        result.new_economic_gain = Decimal("999")


def test_accounting_transition_never_authorizes_fee_or_execution():
    result = apply_attributable_performance(
        initial_performance_account("CAD"),
        _performance(Decimal("10")),
    )

    assert result.real_fee_collection_allowed is False
    assert result.client_funds_deduction_allowed is False
    assert result.execution_authority is False
