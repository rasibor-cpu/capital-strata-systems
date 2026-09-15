from decimal import Decimal
import sqlite3

import backend.app.persistence.migrations.runner as migration_runner
import backend.app.persistence.repositories.base_repository as base_repository
from backend.app.persistence.services.customer_profitability_summary_service import (
    CustomerProfitabilitySummaryService,
)
from backend.app.persistence.services.persistence_service import PersistenceService
from backend.commercialization.billing_profile import (
    BillingPartyType,
    PaymentTermsStatus,
    TaxTreatmentStatus,
    build_commercial_billing_profile,
)
from backend.commercialization.final_fee_selection import build_final_fee_selection
from backend.commercialization.independent_trade_economics import (
    build_independent_trade_economics,
)
from backend.commercialization.performance_accounting import (
    apply_attributable_performance,
    initial_performance_account,
)
from backend.commercialization.performance_attribution import AttributablePerformance
from backend.commercialization.performance_compensation import (
    PerformanceCompensationTerms,
    build_shadow_compensation_entitlement,
)
from backend.commercialization.performance_crystallization import (
    CrystallizationFrequency,
    CrystallizationStatus,
    PerformanceCompensationLifecyclePolicy,
    build_crystallization_assessment,
)
from backend.commercialization.platform_access_fee_terms import (
    CommercialPlatformAccessFeeTerms,
    PlatformAccessBillingFrequency,
)
from backend.commercialization.settlement_readiness import SettlementReadinessStatus
from backend.commercialization.final_fee_settlement_readiness import (
    build_final_fee_settlement_readiness,
)
from backend.commercialization.trade_provenance import (
    AttributionClass,
    MandateCompliance,
    TradeProvenance,
)


START = "2026-09-01T00:00:00Z"
END = "2026-10-01T00:00:00Z"
AT = "2026-09-15T00:00:00Z"
REFS = ("evidence:1",)


def test_service_combines_persisted_css_and_independent_economics(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    monkeypatch.setattr(base_repository, "get_connection", lambda: conn)
    monkeypatch.setattr(migration_runner, "get_connection", lambda: conn)

    try:
        service = PersistenceService()

        access = CommercialPlatformAccessFeeTerms(
            "ACCESS-A", "USD", Decimal("29.99"),
            PlatformAccessBillingFrequency.MONTHLY, START, REFS, True, END,
        )
        terms = PerformanceCompensationTerms(
            "TERMS-A", "USD", Decimal("0.20"), START, REFS, True,
        )
        policy = PerformanceCompensationLifecyclePolicy(
            "POLICY-A", "TERMS-A", "USD",
            CrystallizationFrequency.MONTHLY, START, REFS,
        )
        service.platform_access_fee_terms.create_terms(access)
        service.performance_compensation_terms.create_terms(terms)
        service.performance_compensation_lifecycle_policies.create_policy(policy)
        service.billing_profiles.create_profile(
            build_commercial_billing_profile(
                billing_profile_id="BP-A",
                terms_id="TERMS-A",
                party_type=BillingPartyType.INDIVIDUAL,
                bill_to_name="Client",
                bill_to_reference="account:A",
                seller_reference="seller:CSS",
                tax_treatment_status=TaxTreatmentStatus.OUT_OF_SCOPE,
                payment_terms_status=PaymentTermsStatus.DEFINED_EXTERNALLY,
                effective_from=START,
                effective_to=END,
                evidence_refs=REFS,
            )
        )

        perf = AttributablePerformance(
            trade_id="CSS-1",
            advice_id="ADVICE-1",
            realized_pnl=Decimal("100"),
            currency="USD",
            verification_timestamp=AT,
            provenance_evidence_refs=REFS,
            economics_evidence_refs=REFS,
        )
        transition = apply_attributable_performance(
            initial_performance_account("USD"), perf
        )
        service.performance_accounting_transitions.create_transition(transition)
        entitlement = build_shadow_compensation_entitlement(transition, terms, AT)
        service.shadow_compensation_entitlements.create_entitlement(entitlement)

        assessment = build_crystallization_assessment(
            policy, (entitlement,), START, END, AT,
            CrystallizationStatus.ELIGIBLE, REFS,
        )
        service.crystallization_assessments.create_assessment(assessment)
        selection = build_final_fee_selection(
            access, terms, assessment,
            fee_selection_id="FEE-A",
            period_start=START,
            period_end=END,
            selected_at=AT,
            evidence_refs=REFS,
        )
        service.final_fee_selections.create_selection(selection)
        service.settlement_readiness.create_readiness(
            build_final_fee_settlement_readiness(
                selection, SettlementReadinessStatus.READY, AT, REFS
            )
        )

        independent = build_independent_trade_economics(
            TradeProvenance(
                trade_id="IND-1",
                attribution_class=AttributionClass.CUSTOMER_DIRECTED,
                mandate_compliance=MandateCompliance.OVERRIDDEN,
                evidence_refs=REFS,
            ),
            account_reference="account:A",
            calculation_timestamp=AT,
            realized_pnl=Decimal("50"),
            currency="USD",
            platform_charge_rate=Decimal("0.01"),
            evidence_refs=REFS,
        )
        service.independent_trade_economics.create_record(independent)

        summary = CustomerProfitabilitySummaryService(service).build_summary(
            policy_id="POLICY-A",
            period_start=START,
            period_end=END,
        )
        assert summary.css_realized_profit == Decimal("100")
        assert summary.css_performance_fee == Decimal("20.00")
        assert summary.independent_realized_profit == Decimal("50")
        assert summary.independent_platform_charge == Decimal("0.50")
        assert summary.gross_customer_profit == Decimal("150")
        assert summary.total_css_charges == Decimal("20.50")
        assert summary.net_customer_profit_after_css_charges == Decimal("129.50")
    finally:
        conn.close()
