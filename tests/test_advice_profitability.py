from decimal import Decimal

from backend.commercialization.advice_profitability import (
    build_advice_profitability,
)
from backend.commercialization.performance_accounting import (
    apply_attributable_performance,
    initial_performance_account,
)
from backend.commercialization.performance_attribution import (
    AttributablePerformance,
)


REFS = ("evidence:trade",)


def _performance(trade_id, pnl):
    return AttributablePerformance(
        trade_id=trade_id,
        advice_id=f"ADVICE-{trade_id}",
        realized_pnl=pnl,
        currency="USD",
        verification_timestamp="2026-09-15T00:00:00Z",
        provenance_evidence_refs=REFS,
        economics_evidence_refs=REFS,
    )


def test_profitable_advice_shows_customer_and_css_share():
    state = initial_performance_account("USD")
    perf = _performance("T1", Decimal("100"))
    transition = apply_attributable_performance(state, perf)
    result = build_advice_profitability(
        perf,
        transition,
        performance_fee_rate=Decimal("0.20"),
    )
    assert result.realized_pnl == Decimal("100")
    assert result.new_economic_gain == Decimal("100")
    assert result.css_shadow_fee == Decimal("20.00")
    assert result.customer_retained_after_css_fee == Decimal("80.00")
    assert result.fee_applies is True


def test_loss_has_no_css_fee():
    state = initial_performance_account("USD")
    perf = _performance("T1", Decimal("-50"))
    transition = apply_attributable_performance(state, perf)
    result = build_advice_profitability(
        perf,
        transition,
        performance_fee_rate=Decimal("0.20"),
    )
    assert result.css_shadow_fee == Decimal("0.00")
    assert result.customer_retained_after_css_fee == Decimal("-50.00")
    assert result.fee_applies is False


def test_recovery_only_gain_has_no_css_fee():
    first = _performance("T1", Decimal("-50"))
    state = apply_attributable_performance(
        initial_performance_account("USD"),
        first,
    ).new_state

    perf = _performance("T2", Decimal("40"))
    transition = apply_attributable_performance(state, perf)
    result = build_advice_profitability(
        perf,
        transition,
        performance_fee_rate=Decimal("0.20"),
    )
    assert result.recovered_loss == Decimal("40")
    assert result.new_economic_gain == Decimal("0")
    assert result.css_shadow_fee == Decimal("0.00")
    assert result.customer_retained_after_css_fee == Decimal("40.00")


def test_partial_recovery_then_new_gain_fees_only_fresh_gain():
    first = _performance("T1", Decimal("-50"))
    state = apply_attributable_performance(
        initial_performance_account("USD"),
        first,
    ).new_state

    perf = _performance("T2", Decimal("80"))
    transition = apply_attributable_performance(state, perf)
    result = build_advice_profitability(
        perf,
        transition,
        performance_fee_rate=Decimal("0.20"),
    )
    assert result.recovered_loss == Decimal("50")
    assert result.new_economic_gain == Decimal("30")
    assert result.css_shadow_fee == Decimal("6.00")
    assert result.customer_retained_after_css_fee == Decimal("74.00")


def test_advice_view_has_no_money_or_execution_authority():
    perf = _performance("T1", Decimal("100"))
    transition = apply_attributable_performance(
        initial_performance_account("USD"),
        perf,
    )
    result = build_advice_profitability(
        perf,
        transition,
        performance_fee_rate=Decimal("0.20"),
    )
    assert result.money_movement_allowed is False
    assert result.invoice_creation_allowed is False
    assert result.client_funds_deduction_allowed is False
    assert result.execution_authority is False
