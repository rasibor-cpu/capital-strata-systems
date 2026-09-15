from decimal import Decimal

import pytest

from backend.commercialization.client_earnings_summary import (
    CommercialClientEarningsSummary,
)
from backend.commercialization.final_fee_selection import FinalFeeBasis
from backend.commercialization.independent_trade_economics import (
    build_independent_trade_economics,
)
from backend.commercialization.performance_crystallization import CrystallizationStatus
from backend.commercialization.customer_profitability import (
    CustomerProfitabilityError,
    build_customer_profitability_summary,
)
from backend.commercialization.trade_provenance import (
    AttributionClass,
    MandateCompliance,
    TradeProvenance,
)


REFS = ("evidence:1",)


def _css_summary():
    return CommercialClientEarningsSummary(
        account_reference="account:A",
        policy_id="POLICY-A",
        terms_id="TERMS-A",
        billing_period_start="2026-09-01T00:00:00Z",
        billing_period_end="2026-10-01T00:00:00Z",
        performance_currency="USD",
        billing_currency="USD",
        commercial_status=CrystallizationStatus.ELIGIBLE,
        realized_attributable_profit=Decimal("200"),
        recovered_loss=Decimal("50"),
        new_economic_gain=Decimal("150"),
        performance_fee_rate=Decimal("0.20"),
        performance_fee_source_amount=Decimal("30"),
        performance_fee_billing_currency_amount=Decimal("30"),
        platform_access_fee_amount=Decimal("29.99"),
        access_terms_id="ACCESS-A",
        selected_fee_basis=FinalFeeBasis.PERFORMANCE_COMPENSATION,
        selected_fee_amount=Decimal("30"),
        final_fee_selection_id="FEE-A",
        net_earnings_after_css_fee=Decimal("170"),
        fx_rate=None,
        fx_conversion_id=None,
        fx_rate_source_reference=None,
        invoice_id=None,
        receivable_id=None,
        evidence_refs=REFS,
    )


def _independent(trade_id, pnl, rate=Decimal("0.01"), currency="USD"):
    provenance = TradeProvenance(
        trade_id=trade_id,
        attribution_class=AttributionClass.CUSTOMER_DIRECTED,
        mandate_compliance=MandateCompliance.OVERRIDDEN,
        evidence_refs=(f"prov:{trade_id}",),
    )
    return build_independent_trade_economics(
        provenance,
        realized_pnl=pnl,
        currency=currency,
        platform_charge_rate=rate,
        evidence_refs=(f"econ:{trade_id}",),
    )


def test_combined_profitability_reconciles_separate_streams():
    summary = build_customer_profitability_summary(
        _css_summary(),
        (
            _independent("I1", Decimal("100")),
            _independent("I2", Decimal("-20")),
        ),
    )
    assert summary.css_realized_profit == Decimal("200")
    assert summary.css_recovered_loss == Decimal("50")
    assert summary.css_new_economic_gain == Decimal("150")
    assert summary.css_performance_fee == Decimal("30")

    assert summary.independent_realized_profit == Decimal("80")
    assert summary.independent_platform_charge == Decimal("1.00")
    assert summary.independent_trade_count == 2

    assert summary.gross_customer_profit == Decimal("280")
    assert summary.total_css_charges == Decimal("31.00")
    assert summary.net_customer_profit_after_css_charges == Decimal("249.00")


def test_independent_losses_do_not_create_charge_or_affect_css_hwm_view():
    summary = build_customer_profitability_summary(
        _css_summary(),
        (_independent("I1", Decimal("-100")),),
    )
    assert summary.independent_platform_charge == Decimal("0")
    assert summary.css_recovered_loss == Decimal("50")
    assert summary.css_new_economic_gain == Decimal("150")
    explanation = summary.explain()
    assert explanation["independent_customer_controlled"]["affects_css_hwm"] is False
    assert explanation["independent_customer_controlled"]["affects_css_loss_recovery"] is False


def test_cross_currency_independent_activity_fails_closed():
    with pytest.raises(CustomerProfitabilityError, match="currency must match"):
        build_customer_profitability_summary(
            _css_summary(),
            (_independent("I1", Decimal("100"), currency="CAD"),),
        )


def test_combined_view_has_no_collection_or_execution_authority():
    summary = build_customer_profitability_summary(_css_summary(), ())
    assert summary.money_movement_allowed is False
    assert summary.invoice_creation_allowed is False
    assert summary.client_funds_deduction_allowed is False
    assert summary.execution_authority is False
