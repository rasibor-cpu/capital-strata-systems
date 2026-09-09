from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from backend.commercialization.billable_obligation import (
    BillableObligationStatus,
    CommercialBillableObligation,
)
from backend.commercialization.billing_profile import (
    BillingPartyType,
    CommercialBillingProfile,
    PaymentTermsStatus,
    TaxTreatmentStatus,
    build_commercial_billing_profile,
)
from backend.commercialization.invoice_candidate import (
    CommercialInvoiceCandidate,
    InvoiceCandidateError,
    InvoiceCandidateIneligibleError,
    InvoiceCandidateStatus,
    build_invoice_candidate,
)


PERIOD_START = "2026-03-01T00:00:00+00:00"
PERIOD_END = "2026-04-01T00:00:00+00:00"
RECOGNIZED_AT = "2026-04-03T10:00:00+00:00"
ASSESSED_AT = "2026-04-04T11:00:00+00:00"
PROFILE_FROM = "2026-01-01T00:00:00+00:00"
PROFILE_TO = "2026-12-31T00:00:00+00:00"


def _obligation(
    *,
    status: BillableObligationStatus = BillableObligationStatus.BILLABLE,
    billable_amount: Decimal = Decimal("1"),
    policy_id: str = "POLICY-001",
    terms_id: str = "TERMS-001",
    currency: str = "CAD",
    period_start: str = PERIOD_START,
    period_end: str = PERIOD_END,
) -> CommercialBillableObligation:
    return CommercialBillableObligation(
        policy_id=policy_id,
        terms_id=terms_id,
        currency=currency,
        period_start=period_start,
        period_end=period_end,
        billable_amount=billable_amount,
        recognized_at=RECOGNIZED_AT,
        status=status,
        evidence_refs=("billable:OPS-1",),
    )


def _profile(
    *,
    billing_profile_id: str = "BP-001",
    terms_id: str = "TERMS-001",
    tax_treatment_status: TaxTreatmentStatus = (
        TaxTreatmentStatus.OUT_OF_SCOPE
    ),
    payment_terms_status: PaymentTermsStatus = (
        PaymentTermsStatus.DEFINED_EXTERNALLY
    ),
    effective_from: str = PROFILE_FROM,
    effective_to: str | None = PROFILE_TO,
) -> CommercialBillingProfile:
    return build_commercial_billing_profile(
        billing_profile_id=billing_profile_id,
        terms_id=terms_id,
        party_type=BillingPartyType.ORGANIZATION,
        bill_to_name="Acme Capital Ltd",
        bill_to_reference="BILLTO-ACME-1",
        seller_reference="SELLER-CSS-1",
        tax_treatment_status=tax_treatment_status,
        payment_terms_status=payment_terms_status,
        effective_from=effective_from,
        evidence_refs=("profile:BP-001",),
        effective_to=effective_to,
    )


def test_ready_candidate_from_billable_and_invoice_ready_profile():
    candidate = build_invoice_candidate(
        _obligation(),
        _profile(),
        InvoiceCandidateStatus.READY,
        ASSESSED_AT,
        ("candidate:OPS-1",),
    )

    assert candidate.status is InvoiceCandidateStatus.READY
    assert candidate.policy_id == "POLICY-001"
    assert candidate.terms_id == "TERMS-001"
    assert candidate.billing_profile_id == "BP-001"
    assert candidate.currency == "CAD"
    assert candidate.period_start == PERIOD_START
    assert candidate.period_end == PERIOD_END
    assert candidate.candidate_amount == Decimal("1")


def test_valid_not_ready_candidate():
    candidate = build_invoice_candidate(
        _obligation(),
        _profile(),
        InvoiceCandidateStatus.NOT_READY,
        ASSESSED_AT,
        ("candidate:OPS-1",),
    )

    assert candidate.status is InvoiceCandidateStatus.NOT_READY


def test_valid_blocked_candidate():
    candidate = build_invoice_candidate(
        _obligation(),
        _profile(),
        InvoiceCandidateStatus.BLOCKED,
        ASSESSED_AT,
        ("candidate:OPS-1",),
    )

    assert candidate.status is InvoiceCandidateStatus.BLOCKED


def test_valid_expired_candidate():
    candidate = build_invoice_candidate(
        _obligation(),
        _profile(),
        InvoiceCandidateStatus.EXPIRED,
        ASSESSED_AT,
        ("candidate:OPS-1",),
    )

    assert candidate.status is InvoiceCandidateStatus.EXPIRED


@pytest.mark.parametrize(
    "obligation_status",
    [
        BillableObligationStatus.NOT_BILLABLE,
        BillableObligationStatus.BLOCKED,
        BillableObligationStatus.EXPIRED,
    ],
)
def test_ready_rejected_for_non_billable_obligation(obligation_status):
    with pytest.raises(
        InvoiceCandidateIneligibleError,
        match="READY requires BILLABLE",
    ):
        build_invoice_candidate(
            _obligation(status=obligation_status),
            _profile(),
            InvoiceCandidateStatus.READY,
            ASSESSED_AT,
            ("candidate:OPS-1",),
        )


def test_ready_rejected_when_billing_profile_tax_unresolved():
    with pytest.raises(
        InvoiceCandidateIneligibleError,
        match="invoice-ready billing profile",
    ):
        build_invoice_candidate(
            _obligation(),
            _profile(
                tax_treatment_status=TaxTreatmentStatus.UNDETERMINED,
            ),
            InvoiceCandidateStatus.READY,
            ASSESSED_AT,
            ("candidate:OPS-1",),
        )


def test_ready_rejected_when_billing_profile_payment_terms_unresolved():
    with pytest.raises(
        InvoiceCandidateIneligibleError,
        match="invoice-ready billing profile",
    ):
        build_invoice_candidate(
            _obligation(),
            _profile(
                payment_terms_status=(
                    PaymentTermsStatus.REQUIRES_DEFINITION
                ),
            ),
            InvoiceCandidateStatus.READY,
            ASSESSED_AT,
            ("candidate:OPS-1",),
        )


def test_ready_rejected_on_terms_id_mismatch():
    with pytest.raises(
        InvoiceCandidateError,
        match="terms_id must match",
    ):
        build_invoice_candidate(
            _obligation(terms_id="TERMS-001"),
            _profile(terms_id="TERMS-OTHER"),
            InvoiceCandidateStatus.READY,
            ASSESSED_AT,
            ("candidate:OPS-1",),
        )


def test_construction_rejected_on_terms_id_mismatch_for_non_ready():
    with pytest.raises(
        InvoiceCandidateError,
        match="terms_id must match",
    ):
        build_invoice_candidate(
            _obligation(terms_id="TERMS-001"),
            _profile(terms_id="TERMS-OTHER"),
            InvoiceCandidateStatus.NOT_READY,
            ASSESSED_AT,
            ("candidate:OPS-1",),
        )


def test_billing_profile_effectivity_overlap_accepted():
    candidate = build_invoice_candidate(
        _obligation(),
        _profile(
            effective_from="2026-03-01T00:00:00+00:00",
            effective_to="2026-04-01T00:00:00+00:00",
        ),
        InvoiceCandidateStatus.READY,
        ASSESSED_AT,
        ("candidate:OPS-1",),
    )

    assert candidate.status is InvoiceCandidateStatus.READY


def test_non_overlapping_profile_rejected():
    with pytest.raises(
        InvoiceCandidateError,
        match="must overlap obligation period",
    ):
        build_invoice_candidate(
            _obligation(),
            _profile(
                effective_from="2026-05-01T00:00:00+00:00",
                effective_to="2026-06-01T00:00:00+00:00",
            ),
            InvoiceCandidateStatus.NOT_READY,
            ASSESSED_AT,
            ("candidate:OPS-1",),
        )


def test_zero_candidate_amount_ready_supported():
    candidate = build_invoice_candidate(
        _obligation(billable_amount=Decimal("0")),
        _profile(),
        InvoiceCandidateStatus.READY,
        ASSESSED_AT,
        ("candidate:OPS-1",),
    )

    assert candidate.status is InvoiceCandidateStatus.READY
    assert candidate.candidate_amount == Decimal("0")
    assert candidate.invoice_creation_allowed is False


def test_candidate_amount_copied_exactly():
    obligation = _obligation(billable_amount=Decimal("3.50"))
    candidate = build_invoice_candidate(
        obligation,
        _profile(),
        InvoiceCandidateStatus.READY,
        ASSESSED_AT,
        ("candidate:OPS-1",),
    )

    assert candidate.candidate_amount == Decimal("3.50")
    assert candidate.candidate_amount == obligation.billable_amount


def test_decimal_representation_preserved():
    candidate = build_invoice_candidate(
        _obligation(billable_amount=Decimal("1.00")),
        _profile(),
        InvoiceCandidateStatus.READY,
        ASSESSED_AT,
        ("candidate:OPS-1",),
    )

    assert str(candidate.candidate_amount) == "1.00"


def test_no_economic_recalculation_from_upstream_trade_chain():
    candidate = build_invoice_candidate(
        _obligation(billable_amount=Decimal("1")),
        _profile(),
        InvoiceCandidateStatus.READY,
        ASSESSED_AT,
        ("candidate:OPS-1",),
    )

    assert candidate.candidate_amount == Decimal("1")
    assert candidate.candidate_amount != Decimal("3")
    assert candidate.candidate_amount != Decimal("5")
    assert candidate.candidate_amount != Decimal("15")


def test_blank_billing_profile_id_rejected():
    with pytest.raises(ValueError, match="billing_profile_id"):
        CommercialInvoiceCandidate(
            policy_id="POLICY-001",
            terms_id="TERMS-001",
            billing_profile_id=" ",
            currency="CAD",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            candidate_amount=Decimal("1"),
            assessed_at=ASSESSED_AT,
            status=InvoiceCandidateStatus.NOT_READY,
            evidence_refs=("candidate:OPS-1",),
        )


def test_lowercase_currency_rejected():
    with pytest.raises(ValueError, match="currency"):
        CommercialInvoiceCandidate(
            policy_id="POLICY-001",
            terms_id="TERMS-001",
            billing_profile_id="BP-001",
            currency="cad",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            candidate_amount=Decimal("1"),
            assessed_at=ASSESSED_AT,
            status=InvoiceCandidateStatus.NOT_READY,
            evidence_refs=("candidate:OPS-1",),
        )


def test_invalid_status_rejected():
    with pytest.raises(TypeError, match="InvoiceCandidateStatus"):
        build_invoice_candidate(
            _obligation(),
            _profile(),
            "READY",  # type: ignore[arg-type]
            ASSESSED_AT,
            ("candidate:OPS-1",),
        )


def test_naive_assessed_at_rejected():
    with pytest.raises(ValueError, match="timezone-aware UTC"):
        build_invoice_candidate(
            _obligation(),
            _profile(),
            InvoiceCandidateStatus.NOT_READY,
            "2026-04-04T11:00:00",
            ("candidate:OPS-1",),
        )


def test_non_utc_assessed_at_rejected():
    with pytest.raises(ValueError, match="UTC"):
        build_invoice_candidate(
            _obligation(),
            _profile(),
            InvoiceCandidateStatus.NOT_READY,
            "2026-04-04T11:00:00-04:00",
            ("candidate:OPS-1",),
        )


def test_invalid_period_ordering_rejected():
    with pytest.raises(ValueError, match="period_end must be after"):
        CommercialInvoiceCandidate(
            policy_id="POLICY-001",
            terms_id="TERMS-001",
            billing_profile_id="BP-001",
            currency="CAD",
            period_start=PERIOD_START,
            period_end=PERIOD_START,
            candidate_amount=Decimal("1"),
            assessed_at=ASSESSED_AT,
            status=InvoiceCandidateStatus.NOT_READY,
            evidence_refs=("candidate:OPS-1",),
        )


def test_missing_evidence_rejected():
    with pytest.raises(ValueError, match="evidence_refs"):
        build_invoice_candidate(
            _obligation(),
            _profile(),
            InvoiceCandidateStatus.NOT_READY,
            ASSESSED_AT,
            (),
        )


def test_blank_evidence_ref_rejected():
    with pytest.raises(ValueError, match="evidence refs"):
        build_invoice_candidate(
            _obligation(),
            _profile(),
            InvoiceCandidateStatus.NOT_READY,
            ASSESSED_AT,
            (" ",),
        )


def test_object_immutable():
    candidate = build_invoice_candidate(
        _obligation(),
        _profile(),
        InvoiceCandidateStatus.READY,
        ASSESSED_AT,
        ("candidate:OPS-1",),
    )

    with pytest.raises(FrozenInstanceError):
        candidate.status = InvoiceCandidateStatus.BLOCKED


def test_no_invoice_creation_authority():
    assert (
        build_invoice_candidate(
            _obligation(),
            _profile(),
            InvoiceCandidateStatus.READY,
            ASSESSED_AT,
            ("candidate:OPS-1",),
        ).invoice_creation_allowed
        is False
    )


def test_no_invoice_number_assignment_authority():
    assert (
        build_invoice_candidate(
            _obligation(),
            _profile(),
            InvoiceCandidateStatus.READY,
            ASSESSED_AT,
            ("candidate:OPS-1",),
        ).invoice_number_assignment_allowed
        is False
    )


def test_no_receivable_recognition_authority():
    assert (
        build_invoice_candidate(
            _obligation(),
            _profile(),
            InvoiceCandidateStatus.READY,
            ASSESSED_AT,
            ("candidate:OPS-1",),
        ).receivable_recognition_allowed
        is False
    )


def test_no_ledger_posting_authority():
    assert (
        build_invoice_candidate(
            _obligation(),
            _profile(),
            InvoiceCandidateStatus.READY,
            ASSESSED_AT,
            ("candidate:OPS-1",),
        ).ledger_posting_allowed
        is False
    )


def test_no_revenue_recognition_authority():
    assert (
        build_invoice_candidate(
            _obligation(),
            _profile(),
            InvoiceCandidateStatus.READY,
            ASSESSED_AT,
            ("candidate:OPS-1",),
        ).revenue_recognition_allowed
        is False
    )


def test_no_tax_calculation_authority():
    assert (
        build_invoice_candidate(
            _obligation(),
            _profile(),
            InvoiceCandidateStatus.READY,
            ASSESSED_AT,
            ("candidate:OPS-1",),
        ).tax_calculation_allowed
        is False
    )


def test_no_due_balance_creation_authority():
    assert (
        build_invoice_candidate(
            _obligation(),
            _profile(),
            InvoiceCandidateStatus.READY,
            ASSESSED_AT,
            ("candidate:OPS-1",),
        ).due_balance_creation_allowed
        is False
    )


def test_no_fee_collection_authority():
    assert (
        build_invoice_candidate(
            _obligation(),
            _profile(),
            InvoiceCandidateStatus.READY,
            ASSESSED_AT,
            ("candidate:OPS-1",),
        ).real_fee_collection_allowed
        is False
    )


def test_no_client_funds_deduction_authority():
    assert (
        build_invoice_candidate(
            _obligation(),
            _profile(),
            InvoiceCandidateStatus.READY,
            ASSESSED_AT,
            ("candidate:OPS-1",),
        ).client_funds_deduction_allowed
        is False
    )


def test_no_automatic_debit_authority():
    assert (
        build_invoice_candidate(
            _obligation(),
            _profile(),
            InvoiceCandidateStatus.READY,
            ASSESSED_AT,
            ("candidate:OPS-1",),
        ).automatic_debit_allowed
        is False
    )


def test_no_invoice_settlement_authority():
    assert (
        build_invoice_candidate(
            _obligation(),
            _profile(),
            InvoiceCandidateStatus.READY,
            ASSESSED_AT,
            ("candidate:OPS-1",),
        ).invoice_settlement_allowed
        is False
    )


def test_no_payment_initiation_authority():
    assert (
        build_invoice_candidate(
            _obligation(),
            _profile(),
            InvoiceCandidateStatus.READY,
            ASSESSED_AT,
            ("candidate:OPS-1",),
        ).payment_initiation_allowed
        is False
    )


def test_no_money_movement_authority():
    assert (
        build_invoice_candidate(
            _obligation(),
            _profile(),
            InvoiceCandidateStatus.READY,
            ASSESSED_AT,
            ("candidate:OPS-1",),
        ).money_movement_allowed
        is False
    )


def test_no_broker_withdrawal_authority():
    assert (
        build_invoice_candidate(
            _obligation(),
            _profile(),
            InvoiceCandidateStatus.READY,
            ASSESSED_AT,
            ("candidate:OPS-1",),
        ).broker_withdrawal_allowed
        is False
    )


def test_no_execution_authority():
    assert (
        build_invoice_candidate(
            _obligation(),
            _profile(),
            InvoiceCandidateStatus.READY,
            ASSESSED_AT,
            ("candidate:OPS-1",),
        ).execution_authority
        is False
    )
