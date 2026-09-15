from decimal import Decimal

from backend.commercialization.final_fee_selection import FinalFeeBasis
from backend.commercialization.independent_trade_economics import (
    build_independent_trade_economics,
)
from backend.commercialization.trade_provenance import (
    AttributionClass,
    MandateCompliance,
    TradeProvenance,
)
from backend.commercialization.trial_contract import (
    CommercialAgreementSnapshot,
    TrialConversionStatus,
    TrialEnrollment,
    assess_trial_conversion,
)
from dashboard.web.web_app import _billing_page


REFS = ("audit:commercialization",)


def test_billing_ui_contains_no_obsolete_platform_minimum_override_language():
    markup = _billing_page()
    assert "higher of your platform minimum or your performance fee" not in markup
    assert "PLATFORM MINIMUM APPLIED" not in markup
    assert "Platform access reference" in markup
    assert "Final CSS performance charge" in markup
    assert "Advice Profitability History" in markup


def test_customer_directed_economics_never_becomes_performance_fee_eligible():
    provenance = TradeProvenance(
        trade_id="IND-1",
        attribution_class=AttributionClass.CUSTOMER_DIRECTED,
        mandate_compliance=MandateCompliance.OVERRIDDEN,
        evidence_refs=REFS,
    )
    record = build_independent_trade_economics(
        provenance,
        account_reference="account:A",
        calculation_timestamp="2026-09-15T00:00:00Z",
        realized_pnl=Decimal("100"),
        currency="USD",
        platform_charge_rate=Decimal("0.01"),
        evidence_refs=REFS,
    )
    assert record.performance_fee_eligible is False
    assert record.high_water_mark_affected is False
    assert record.loss_recovery_affected is False
    assert record.real_fee_collection_allowed is False


def test_trial_conversion_eligibility_never_implies_payment_authority():
    disclosure = (
        "Your free trial ends on 2026-10-01T00:00:00Z. If you do not cancel "
        "before that time, your paid CSS service begins automatically."
    )
    pricing = "20% of qualifying CSS new economic gain."
    agreement = CommercialAgreementSnapshot(
        agreement_id="AGR-1",
        agreement_version="v1",
        jurisdiction_code="CA-ON",
        pricing_plan_id="PLAN-A",
        pricing_summary=pricing,
        trial_duration_days=30,
        automatic_conversion_disclosure=disclosure,
        effective_from="2026-09-01T00:00:00Z",
        evidence_refs=REFS,
    )
    enrollment = TrialEnrollment(
        customer_id="CUST-1",
        account_reference="account:A",
        agreement_id="AGR-1",
        agreement_version="v1",
        pricing_plan_id="PLAN-A",
        accepted_at="2026-09-01T00:00:00Z",
        trial_start_at="2026-09-01T00:00:00Z",
        trial_expires_at="2026-10-01T00:00:00Z",
        displayed_pricing_summary=pricing,
        displayed_conversion_disclosure=disclosure,
        acceptance_audit_reference="accept:1",
        evidence_refs=REFS,
    )
    assessment = assess_trial_conversion(
        agreement,
        enrollment,
        assessed_at="2026-10-02T00:00:00Z",
    )
    assert assessment.status is TrialConversionStatus.ELIGIBLE_TO_CONVERT
    assert assessment.automatic_conversion_allowed is True
    assert assessment.money_movement_allowed is False
    assert assessment.payment_execution_allowed is False
    assert assessment.execution_authority is False


def test_production_commercialization_remains_fail_closed():
    # The costing/legal foundation may classify economics or documentary
    # conversion eligibility, but no object introduced in this increment
    # grants customer-funds or execution authority.
    markup = _billing_page()
    assert "No payment execution from this view" in markup
    assert "Read-only presentation" in markup
