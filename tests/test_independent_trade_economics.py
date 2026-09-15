from decimal import Decimal

import pytest

from backend.commercialization.independent_trade_economics import (
    IndependentTradeChargeBasis,
    IndependentTradeEconomicsIneligibleError,
    build_independent_trade_economics,
)
from backend.commercialization.trade_provenance import (
    AttributionClass,
    MandateCompliance,
    TradeProvenance,
)


REFS = ("trade:audit",)


def _prov(attribution_class, mandate):
    kwargs = {}
    if attribution_class == AttributionClass.CSS_ADVISED_ACCEPTED:
        kwargs.update(
            advice_id="ADVICE-1",
            acceptance_timestamp="2026-09-15T00:00:00Z",
            evidence_refs=REFS,
        )
    else:
        kwargs["evidence_refs"] = REFS
    return TradeProvenance(
        trade_id="TRADE-1",
        attribution_class=attribution_class,
        mandate_compliance=mandate,
        **kwargs,
    )


def test_customer_directed_trade_uses_separate_platform_economics():
    record = build_independent_trade_economics(
        _prov(AttributionClass.CUSTOMER_DIRECTED, MandateCompliance.OVERRIDDEN),
        account_reference="account:A",
        calculation_timestamp="2026-09-15T00:00:00Z",
        realized_pnl=Decimal("100"),
        currency="USD",
        platform_charge_rate=Decimal("0.01"),
        evidence_refs=REFS,
    )
    assert record.platform_charge_amount == Decimal("1.00")
    assert record.charge_basis is IndependentTradeChargeBasis.PLATFORM_USAGE
    assert record.css_performance_attributable is False
    assert record.high_water_mark_affected is False
    assert record.loss_recovery_affected is False
    assert record.performance_fee_eligible is False


def test_css_modified_trade_is_independent_not_performance_attributable():
    record = build_independent_trade_economics(
        _prov(AttributionClass.CSS_MODIFIED, MandateCompliance.MODIFIED),
        account_reference="account:A",
        calculation_timestamp="2026-09-15T00:00:00Z",
        realized_pnl=Decimal("80"),
        currency="CAD",
        platform_charge_rate=Decimal("0.005"),
        evidence_refs=REFS,
    )
    assert record.platform_charge_amount == Decimal("0.400")
    assert record.css_performance_attributable is False


def test_independent_trade_loss_never_creates_platform_charge():
    record = build_independent_trade_economics(
        _prov(AttributionClass.CUSTOMER_DIRECTED, MandateCompliance.OVERRIDDEN),
        account_reference="account:A",
        calculation_timestamp="2026-09-15T00:00:00Z",
        realized_pnl=Decimal("-250"),
        currency="USD",
        platform_charge_rate=Decimal("0.01"),
        evidence_refs=REFS,
    )
    assert record.platform_charge_amount == Decimal("0")


def test_css_accepted_trade_cannot_enter_independent_path():
    with pytest.raises(
        IndependentTradeEconomicsIneligibleError,
        match="performance-fee path",
    ):
        build_independent_trade_economics(
            _prov(AttributionClass.CSS_ADVISED_ACCEPTED, MandateCompliance.COMPLIANT),
            account_reference="account:A",
        calculation_timestamp="2026-09-15T00:00:00Z",
        realized_pnl=Decimal("100"),
            currency="USD",
            platform_charge_rate=Decimal("0.01"),
            evidence_refs=REFS,
        )


def test_external_trade_cannot_create_css_economics():
    with pytest.raises(
        IndependentTradeEconomicsIneligibleError,
        match="external trades are excluded",
    ):
        build_independent_trade_economics(
            _prov(AttributionClass.EXTERNAL, MandateCompliance.OUTSIDE_CSS),
            account_reference="account:A",
        calculation_timestamp="2026-09-15T00:00:00Z",
        realized_pnl=Decimal("100"),
            currency="USD",
            platform_charge_rate=Decimal("0.01"),
            evidence_refs=REFS,
        )


def test_shadow_record_has_no_money_or_execution_authority():
    record = build_independent_trade_economics(
        _prov(AttributionClass.CUSTOMER_DIRECTED, MandateCompliance.OVERRIDDEN),
        account_reference="account:A",
        calculation_timestamp="2026-09-15T00:00:00Z",
        realized_pnl=Decimal("100"),
        currency="USD",
        platform_charge_rate=Decimal("0.01"),
        evidence_refs=REFS,
    )
    assert record.real_fee_collection_allowed is False
    assert record.client_funds_deduction_allowed is False
    assert record.money_movement_allowed is False
    assert record.invoice_creation_allowed is False
    assert record.execution_authority is False
