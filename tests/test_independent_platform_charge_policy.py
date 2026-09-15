from decimal import Decimal

import pytest

from backend.commercialization.independent_platform_charge_policy import (
    IndependentPlatformChargeModel,
    IndependentPlatformChargePolicy,
    build_policy_governed_independent_trade_economics,
)
from backend.commercialization.trade_provenance import (
    AttributionClass,
    MandateCompliance,
    TradeProvenance,
)


REFS = ("evidence:1",)


def _provenance():
    return TradeProvenance(
        trade_id="IND-1",
        attribution_class=AttributionClass.CUSTOMER_DIRECTED,
        mandate_compliance=MandateCompliance.OVERRIDDEN,
        evidence_refs=REFS,
    )


def test_unapproved_independent_charge_policy_fails_closed():
    policy = IndependentPlatformChargePolicy(
        policy_id="IND-POLICY-DRAFT",
        model=IndependentPlatformChargeModel.POSITIVE_REALIZED_PERCENTAGE,
        rate=Decimal("0.01"),
        currency="USD",
        approved_for_production=False,
        approved_at=None,
        approval_reference=None,
        evidence_refs=REFS,
    )
    with pytest.raises(ValueError, match="not production approved"):
        build_policy_governed_independent_trade_economics(
            _provenance(),
            account_reference="account:A",
            calculation_timestamp="2026-09-15T00:00:00Z",
            realized_pnl=Decimal("100"),
            currency="USD",
            policy=policy,
            evidence_refs=REFS,
        )


def test_disabled_policy_cannot_create_charge():
    policy = IndependentPlatformChargePolicy(
        policy_id="IND-POLICY-DISABLED",
        model=IndependentPlatformChargeModel.DISABLED,
        rate=Decimal("0"),
        currency="USD",
        approved_for_production=False,
        approved_at=None,
        approval_reference=None,
        evidence_refs=REFS,
    )
    with pytest.raises(ValueError, match="disabled"):
        build_policy_governed_independent_trade_economics(
            _provenance(),
            account_reference="account:A",
            calculation_timestamp="2026-09-15T00:00:00Z",
            realized_pnl=Decimal("100"),
            currency="USD",
            policy=policy,
            evidence_refs=REFS,
        )


def test_approved_percentage_policy_remains_non_performance_and_shadow_only():
    policy = IndependentPlatformChargePolicy(
        policy_id="IND-POLICY-APPROVED",
        model=IndependentPlatformChargeModel.POSITIVE_REALIZED_PERCENTAGE,
        rate=Decimal("0.01"),
        currency="USD",
        approved_for_production=True,
        approved_at="2026-10-01T00:00:00Z",
        approval_reference="commercial:counsel-approved",
        evidence_refs=("policy:evidence",),
    )
    result = build_policy_governed_independent_trade_economics(
        _provenance(),
        account_reference="account:A",
        calculation_timestamp="2026-10-02T00:00:00Z",
        realized_pnl=Decimal("100"),
        currency="USD",
        policy=policy,
        evidence_refs=("trade:evidence",),
    )
    assert result.platform_charge_amount == Decimal("1.00")
    assert result.performance_fee_eligible is False
    assert result.high_water_mark_affected is False
    assert result.real_fee_collection_allowed is False
