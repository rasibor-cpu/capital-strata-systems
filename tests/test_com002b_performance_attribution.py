from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from backend.commercialization.performance_attribution import (
    AttributablePerformance,
    PerformanceAttributionIneligibleError,
    VerifiedTradeEconomics,
    build_attributable_performance,
)
from backend.commercialization.trade_provenance import (
    AttributionClass,
    MandateCompliance,
    TradeProvenance,
)


def _eligible_provenance(
    trade_id: str = "TRADE-001",
) -> TradeProvenance:
    return TradeProvenance(
        trade_id=trade_id,
        advice_id="ADVICE-001",
        attribution_class=AttributionClass.CSS_ADVISED_ACCEPTED,
        mandate_compliance=MandateCompliance.COMPLIANT,
        recommendation_timestamp="2026-09-08T18:00:00Z",
        acceptance_timestamp="2026-09-08T18:01:00Z",
        evidence_refs=("trade-card:ADVICE-001",),
    )


def _economics(
    pnl: Decimal = Decimal("125.50"),
    trade_id: str = "TRADE-001",
) -> VerifiedTradeEconomics:
    return VerifiedTradeEconomics(
        trade_id=trade_id,
        realized_pnl=pnl,
        currency="CAD",
        verification_timestamp="2026-09-08T18:10:00Z",
        evidence_refs=("canonical-pnl:TRADE-001",),
    )


def test_verified_profit_is_attributable():
    result = build_attributable_performance(
        _eligible_provenance(),
        _economics(Decimal("125.50")),
    )

    assert isinstance(result, AttributablePerformance)
    assert result.realized_pnl == Decimal("125.50")


def test_verified_loss_is_equally_attributable():
    result = build_attributable_performance(
        _eligible_provenance(),
        _economics(Decimal("-42.75")),
    )

    assert result.realized_pnl == Decimal("-42.75")


def test_zero_realized_pnl_is_valid():
    result = build_attributable_performance(
        _eligible_provenance(),
        _economics(Decimal("0")),
    )

    assert result.realized_pnl == Decimal("0")


def test_customer_directed_profit_is_excluded():
    provenance = TradeProvenance(
        trade_id="TRADE-001",
        attribution_class=AttributionClass.CUSTOMER_DIRECTED,
        mandate_compliance=MandateCompliance.OUTSIDE_CSS,
        evidence_refs=("customer-order:TRADE-001",),
    )

    with pytest.raises(PerformanceAttributionIneligibleError):
        build_attributable_performance(
            provenance,
            _economics(Decimal("10000")),
        )


def test_modified_css_trade_is_excluded():
    provenance = TradeProvenance(
        trade_id="TRADE-001",
        advice_id="ADVICE-001",
        attribution_class=AttributionClass.CSS_MODIFIED,
        mandate_compliance=MandateCompliance.MODIFIED,
        acceptance_timestamp="2026-09-08T18:01:00Z",
        evidence_refs=("customer-modification:TRADE-001",),
    )

    with pytest.raises(PerformanceAttributionIneligibleError):
        build_attributable_performance(
            provenance,
            _economics(Decimal("500")),
        )


def test_external_profit_is_excluded():
    provenance = TradeProvenance(
        trade_id="TRADE-001",
        attribution_class=AttributionClass.EXTERNAL,
        mandate_compliance=MandateCompliance.OUTSIDE_CSS,
        evidence_refs=("broker-import:TRADE-001",),
    )

    with pytest.raises(PerformanceAttributionIneligibleError):
        build_attributable_performance(
            provenance,
            _economics(Decimal("900")),
        )


def test_trade_id_mismatch_fails_closed():
    with pytest.raises(
        PerformanceAttributionIneligibleError,
        match="trade_id mismatch",
    ):
        build_attributable_performance(
            _eligible_provenance("TRADE-001"),
            _economics(
                Decimal("50"),
                trade_id="TRADE-OTHER",
            ),
        )


def test_float_realized_pnl_is_rejected():
    with pytest.raises(TypeError, match="must be Decimal"):
        VerifiedTradeEconomics(
            trade_id="TRADE-001",
            realized_pnl=12.5,
            currency="CAD",
            verification_timestamp="2026-09-08T18:10:00Z",
            evidence_refs=("canonical-pnl:TRADE-001",),
        )


def test_non_finite_realized_pnl_is_rejected():
    with pytest.raises(ValueError, match="must be finite"):
        _economics(Decimal("NaN"))


def test_economics_requires_evidence():
    with pytest.raises(ValueError, match="require evidence"):
        VerifiedTradeEconomics(
            trade_id="TRADE-001",
            realized_pnl=Decimal("1"),
            currency="CAD",
            verification_timestamp="2026-09-08T18:10:00Z",
            evidence_refs=(),
        )


def test_currency_must_be_canonical_uppercase():
    with pytest.raises(ValueError, match="canonical uppercase"):
        VerifiedTradeEconomics(
            trade_id="TRADE-001",
            realized_pnl=Decimal("1"),
            currency="cad",
            verification_timestamp="2026-09-08T18:10:00Z",
            evidence_refs=("canonical-pnl:TRADE-001",),
        )


def test_attributable_record_is_immutable():
    result = build_attributable_performance(
        _eligible_provenance(),
        _economics(),
    )

    with pytest.raises(FrozenInstanceError):
        result.realized_pnl = Decimal("999")


def test_increment1_never_authorizes_fee_or_execution():
    result = build_attributable_performance(
        _eligible_provenance(),
        _economics(),
    )

    assert result.real_fee_collection_allowed is False
    assert result.client_funds_deduction_allowed is False
    assert result.execution_authority is False
