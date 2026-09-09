from dataclasses import FrozenInstanceError
from decimal import Decimal, localcontext
import sqlite3

import pytest

import backend.app.persistence.repositories.base_repository as base_repository
import backend.app.persistence.migrations.runner as migration_runner
from backend.app.persistence.services.persistence_service import PersistenceService
from backend.app.persistence.services.client_earnings_summary_service import (
    ClientEarningsSummaryService,
)
from backend.commercialization.client_earnings_summary import (
    ClientEarningsSummaryUnavailableError,
    CLIENT_LANGUAGE_FEE_RULE,
)
from backend.commercialization.final_fee_selection import (
    FinalFeeBasis, build_final_fee_selection,
)
from backend.commercialization.fx_conversion import build_fx_conversion_evidence
from backend.commercialization.performance_accounting import (
    PerformanceAccountState, apply_attributable_performance,
    initial_performance_account,
)
from backend.commercialization.performance_attribution import AttributablePerformance
from backend.commercialization.trade_provenance import (
    AttributionClass, MandateCompliance, TradeProvenance,
)
from backend.commercialization.performance_compensation import (
    PerformanceCompensationTerms, build_shadow_compensation_entitlement,
)
from backend.commercialization.performance_crystallization import (
    CrystallizationFrequency, CrystallizationStatus,
    PerformanceCompensationLifecyclePolicy, build_crystallization_assessment,
)
from backend.commercialization.platform_access_fee_terms import (
    CommercialPlatformAccessFeeTerms, PlatformAccessBillingFrequency,
)
from backend.commercialization.billing_profile import (
    BillingPartyType, PaymentTermsStatus, TaxTreatmentStatus,
    build_commercial_billing_profile,
)
from backend.commercialization.invoice_candidate import (
    InvoiceCandidateStatus, build_invoice_candidate,
)
from backend.commercialization.invoice_identity import build_invoice_identity_allocation
from backend.commercialization.invoice_issued import build_invoice_issued_record
from backend.commercialization.receivable_recognition import build_receivable_recognition
from backend.commercialization.settlement_readiness import SettlementReadinessStatus
from backend.commercialization.final_fee_settlement_readiness import (
    build_final_fee_settlement_readiness,
)
from backend.commercialization.billable_obligation import (
    BillableObligationStatus, build_billable_obligation,
)


START = "2026-09-01T00:00:00Z"
END = "2026-10-01T00:00:00Z"
AT = "2026-09-15T00:00:00Z"
REFS = ("contract:approved", "review:commercial")

ACCESS_FEE = Decimal("29.99")


@pytest.fixture
def service(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    monkeypatch.setattr(base_repository, "get_connection", lambda: conn)
    monkeypatch.setattr(migration_runner, "get_connection", lambda: conn)
    try:
        yield PersistenceService()
    finally:
        conn.close()


def _access_terms():
    return CommercialPlatformAccessFeeTerms(
        "ACCESS-A", "USD", ACCESS_FEE, PlatformAccessBillingFrequency.MONTHLY,
        START, REFS, True, END,
    )


def _billing_profile():
    return build_commercial_billing_profile(
        billing_profile_id="BP-A", terms_id="TERMS-A", party_type=BillingPartyType.INDIVIDUAL,
        bill_to_name="Example Client", bill_to_reference="account:CLIENT-001",
        seller_reference="seller:CSS", tax_treatment_status=TaxTreatmentStatus.OUT_OF_SCOPE,
        payment_terms_status=PaymentTermsStatus.DEFINED_EXTERNALLY,
        effective_from=START, effective_to=END, evidence_refs=REFS,
    )


def _seed_trade(service, trade_id, currency, pnl):
    """Persist the COM-002A/B chain required for one attributable trade."""

    service.trades.create_trade(
        trade_id=trade_id, session_id="SESSION-A", broker_name="SIM", broker_mode="paper",
        symbol="EURUSD", direction="LONG", status="closed", order_type="MARKET",
        quantity=Decimal("1"), filled_quantity=Decimal("1"), entry_price=Decimal("1"),
        opened_at=AT,
    )
    service.trade_provenance.create_provenance(TradeProvenance(
        trade_id=trade_id, attribution_class=AttributionClass.CSS_ADVISED_ACCEPTED,
        mandate_compliance=MandateCompliance.COMPLIANT, advice_id="ADVICE-A",
        recommendation_timestamp=AT, acceptance_timestamp=AT, evidence_refs=REFS,
    ))
    service.attributable_performance.create_attributable_performance(AttributablePerformance(
        trade_id=trade_id, advice_id="ADVICE-A", realized_pnl=pnl, currency=currency,
        verification_timestamp=AT, provenance_evidence_refs=REFS, economics_evidence_refs=REFS,
    ))


def build_chain(
    service,
    *,
    trades,  # sequence of (trade_id, pnl) applied sequentially
    currency="USD",
    rate=Decimal("0.20"),
    fx_rate=None,
):
    """Persist a full COM-002A..E chain, returning (selection, assessment, obligation)."""

    access = _access_terms()
    terms = PerformanceCompensationTerms("TERMS-A", currency, rate, START, REFS, True)
    policy = PerformanceCompensationLifecyclePolicy(
        "POLICY-A", "TERMS-A", currency, CrystallizationFrequency.MONTHLY, START, REFS,
    )
    service.platform_access_fee_terms.create_terms(access)
    service.performance_compensation_terms.create_terms(terms)
    service.performance_compensation_lifecycle_policies.create_policy(policy)
    service.billing_profiles.create_profile(_billing_profile())
    service.sessions.create_session(
        session_id="SESSION-A", status="closed", mode="paper",
        broker_name="SIM", broker_mode="paper", started_at=AT,
    )

    state = initial_performance_account(currency)
    entitlements = []
    with localcontext() as context:
        context.prec = 60
        for index, (trade_id, pnl) in enumerate(trades):
            _seed_trade(service, trade_id, currency, pnl)
            transition = apply_attributable_performance(
                state,
                AttributablePerformance(
                    trade_id=trade_id, advice_id="ADVICE-A", realized_pnl=pnl, currency=currency,
                    verification_timestamp=AT, provenance_evidence_refs=REFS, economics_evidence_refs=REFS,
                ),
            )
            service.performance_accounting_transitions.create_transition(transition)
            entitlement = build_shadow_compensation_entitlement(transition, terms, AT)
            service.shadow_compensation_entitlements.create_entitlement(entitlement)
            entitlements.append(entitlement)
            state = transition.new_state

        assessment = build_crystallization_assessment(
            policy, tuple(entitlements), START, END, AT, CrystallizationStatus.ELIGIBLE, REFS,
        )
        service.crystallization_assessments.create_assessment(assessment)

        conversion = None
        if currency != "USD":
            conversion = build_fx_conversion_evidence(
                fx_conversion_id="FX-A", source_currency=currency, target_currency="USD",
                source_amount=assessment.crystallizable_amount, fx_rate=fx_rate,
                rate_effective_at=AT, rate_source_reference="daily:approved", evidence_refs=REFS,
            )
            service.fx_conversion_evidence.create_conversion(conversion)

        selection = build_final_fee_selection(
            access, terms, assessment, fee_selection_id="FEE-A", period_start=START,
            period_end=END, selected_at=AT, evidence_refs=REFS, fx_conversion=conversion,
        )
    service.final_fee_selections.create_selection(selection)

    readiness = build_final_fee_settlement_readiness(selection, SettlementReadinessStatus.READY, AT, REFS)
    service.settlement_readiness.create_readiness(readiness)
    obligation = build_billable_obligation(readiness, BillableObligationStatus.BILLABLE, AT, REFS)
    service.billable_obligations.create_obligation(obligation)

    return selection, assessment, obligation


def issue_invoice_and_receivable(service, obligation):
    billing = _billing_profile()
    candidate = build_invoice_candidate(obligation, billing, InvoiceCandidateStatus.READY, AT, REFS)
    service.invoice_candidates.create_candidate(candidate)
    identity = build_invoice_identity_allocation(
        candidate, invoice_id="INV-A", invoice_number="CSS-001", allocated_at=AT, evidence_refs=REFS,
    )
    service.invoice_identity_allocations.create_allocation(identity)
    issued = build_invoice_issued_record(identity, issued_at=AT, evidence_refs=REFS)
    service.invoice_issued_records.create_issued_record(issued)
    receivable = build_receivable_recognition(issued, receivable_id="REC-A", recognized_at=AT, evidence_refs=REFS)
    service.receivable_recognitions.create_recognition(receivable)
    return issued, receivable


def summarize(service):
    return ClientEarningsSummaryService(service).build_summary("POLICY-A", START, END)


def test_zero_performance_platform_minimum_applies(service):
    build_chain(service, trades=[("T1", Decimal("0"))])
    summary = summarize(service)
    assert summary.new_economic_gain == Decimal("0")
    assert summary.selected_fee_basis is FinalFeeBasis.PLATFORM_ACCESS
    assert summary.selected_fee_amount == ACCESS_FEE


def test_low_performance_below_minimum_platform_minimum_applies(service):
    build_chain(service, trades=[("T1", Decimal("100"))])  # entitlement = 100*0.20 = 20 < 29.99
    summary = summarize(service)
    assert summary.performance_fee_billing_currency_amount == Decimal("20")
    assert summary.selected_fee_basis is FinalFeeBasis.PLATFORM_ACCESS
    assert summary.selected_fee_amount == ACCESS_FEE


def test_exact_tie_performance_fee_applies(service):
    build_chain(service, trades=[("T1", Decimal("149.95"))])  # 149.95*0.20 = 29.99
    summary = summarize(service)
    assert summary.performance_fee_billing_currency_amount == ACCESS_FEE
    assert summary.selected_fee_basis is FinalFeeBasis.PERFORMANCE_COMPENSATION
    assert summary.selected_fee_amount == ACCESS_FEE


def test_performance_above_minimum_performance_fee_applies(service):
    build_chain(service, trades=[("T1", Decimal("750"))])  # 750*0.20 = 150
    summary = summarize(service)
    assert summary.performance_fee_billing_currency_amount == Decimal("150")
    assert summary.selected_fee_basis is FinalFeeBasis.PERFORMANCE_COMPENSATION
    assert summary.selected_fee_amount == Decimal("150")


def test_non_usd_account_fx_normalization(service):
    build_chain(service, trades=[("T1", Decimal("500"))], currency="CAD", fx_rate=Decimal("0.75"))
    # entitlement = 500*0.20 = 100 CAD -> 100*0.75 = 75 USD
    summary = summarize(service)
    assert summary.performance_currency == "CAD"
    assert summary.billing_currency == "USD"
    assert summary.performance_fee_source_amount == Decimal("100")
    assert summary.performance_fee_billing_currency_amount == Decimal("75")
    assert summary.fx_rate == Decimal("0.75")
    assert summary.fx_conversion_id == "FX-A"
    assert summary.selected_fee_basis is FinalFeeBasis.PERFORMANCE_COMPENSATION
    assert summary.fx_language is not None


def test_prior_loss_recovery_gross_gain_exists_but_new_gain_lower(service):
    build_chain(service, trades=[("T1", Decimal("-50")), ("T2", Decimal("80"))])
    summary = summarize(service)
    assert summary.realized_attributable_profit == Decimal("30")  # -50 + 80
    assert summary.recovered_loss == Decimal("50")
    assert summary.new_economic_gain == Decimal("30")  # only the excess above prior HWM


def test_full_loss_recovery_zero_new_economic_gain(service):
    build_chain(service, trades=[("T1", Decimal("-50")), ("T2", Decimal("50"))])
    summary = summarize(service)
    assert summary.realized_attributable_profit == Decimal("0")
    assert summary.recovered_loss == Decimal("50")
    assert summary.new_economic_gain == Decimal("0")
    assert summary.selected_fee_basis is FinalFeeBasis.PLATFORM_ACCESS
    assert summary.selected_fee_amount == ACCESS_FEE


def test_blocked_not_ready_period_has_no_fee_fields(service):
    access = _access_terms()
    terms = PerformanceCompensationTerms("TERMS-A", "USD", Decimal("0.20"), START, REFS, True)
    policy = PerformanceCompensationLifecyclePolicy(
        "POLICY-A", "TERMS-A", "USD", CrystallizationFrequency.MONTHLY, START, REFS,
    )
    service.platform_access_fee_terms.create_terms(access)
    service.performance_compensation_terms.create_terms(terms)
    service.performance_compensation_lifecycle_policies.create_policy(policy)
    service.billing_profiles.create_profile(_billing_profile())
    assessment = build_crystallization_assessment(
        policy, (), START, END, AT, CrystallizationStatus.BLOCKED, REFS,
    )
    service.crystallization_assessments.create_assessment(assessment)

    summary = summarize(service)
    assert summary.commercial_status is CrystallizationStatus.BLOCKED
    assert summary.selected_fee_basis is None
    assert summary.selected_fee_amount is None
    assert summary.net_earnings_after_css_fee is None
    assert summary.invoice_id is None
    assert summary.receivable_id is None


def test_invoice_issued_reflected_in_summary(service):
    _, _, obligation = build_chain(service, trades=[("T1", Decimal("750"))])
    issue_invoice_and_receivable(service, obligation)
    summary = summarize(service)
    assert summary.invoice_id == "INV-A"


def test_receivable_recognized_reflected_in_summary(service):
    _, _, obligation = build_chain(service, trades=[("T1", Decimal("750"))])
    issue_invoice_and_receivable(service, obligation)
    summary = summarize(service)
    assert summary.receivable_id == "REC-A"


def test_missing_canonical_source_fails_closed(service):
    with pytest.raises(ClientEarningsSummaryUnavailableError):
        ClientEarningsSummaryService(service).build_summary("POLICY-MISSING", START, END)


def test_no_additive_charging(service):
    build_chain(service, trades=[("T1", Decimal("750"))])
    summary = summarize(service)
    assert summary.selected_fee_amount != summary.platform_access_fee_amount + summary.performance_fee_billing_currency_amount
    assert summary.selected_fee_amount == max(
        summary.platform_access_fee_amount, summary.performance_fee_billing_currency_amount,
    )


def test_exact_decimal_preservation(service):
    exact = Decimal("149.12345678901234567890123456789")
    build_chain(service, trades=[("T1", exact)], rate=Decimal("1"))
    summary = summarize(service)
    assert summary.performance_fee_billing_currency_amount.as_tuple() == exact.as_tuple()


def test_correct_period_reported(service):
    build_chain(service, trades=[("T1", Decimal("0"))])
    summary = summarize(service)
    assert summary.billing_period_start == START
    assert summary.billing_period_end == END


def test_client_language_fee_rule_present(service):
    build_chain(service, trades=[("T1", Decimal("0"))])
    summary = summarize(service)
    assert summary.fee_rule_language == CLIENT_LANGUAGE_FEE_RULE
    explanation = summary.explain()
    assert explanation["D_final_charge"]["client_language"] == CLIENT_LANGUAGE_FEE_RULE
    assert explanation["D_final_charge"]["customer_pays_both"] is False


def test_projection_is_immutable(service):
    build_chain(service, trades=[("T1", Decimal("0"))])
    summary = summarize(service)
    with pytest.raises(FrozenInstanceError):
        summary.selected_fee_amount = Decimal("1")


def test_scenario_a_cad_150_client_example(service):
    # Qualifying new gain = CAD 150 (crystallizable amount), rate 0.20 -> entitlement
    # comes from gross gain of 750 CAD * 0.20 = 150 CAD, normalized at 0.75 -> 112.50 USD.
    build_chain(service, trades=[("T1", Decimal("750"))], currency="CAD", fx_rate=Decimal("0.75"))
    summary = summarize(service)
    assert summary.performance_fee_source_amount == Decimal("150")
    assert summary.performance_fee_billing_currency_amount == Decimal("112.50")
    assert summary.selected_fee_basis is FinalFeeBasis.PERFORMANCE_COMPENSATION
    assert summary.selected_fee_amount == Decimal("112.50")


def test_scenario_b_cad_20_client_example(service):
    # Qualifying new gain = CAD 20 (crystallizable amount): gross gain 100 CAD * 0.20 = 20 CAD,
    # normalized at 0.75 -> 15 USD, below the USD 29.99 platform minimum.
    build_chain(service, trades=[("T1", Decimal("100"))], currency="CAD", fx_rate=Decimal("0.75"))
    summary = summarize(service)
    assert summary.performance_fee_source_amount == Decimal("20")
    assert summary.performance_fee_billing_currency_amount == Decimal("15")
    assert summary.selected_fee_basis is FinalFeeBasis.PLATFORM_ACCESS
    assert summary.selected_fee_amount == ACCESS_FEE
