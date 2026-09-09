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
    InvoiceCandidateStatus,
    build_invoice_candidate,
)
from backend.commercialization.invoice_identity import (
    CommercialInvoiceIdentityAllocation,
    InvoiceIdentityIneligibleError,
    build_invoice_identity_allocation,
)


PERIOD_START = "2026-03-01T00:00:00+00:00"
PERIOD_END = "2026-04-01T00:00:00+00:00"
RECOGNIZED_AT = "2026-04-03T10:00:00+00:00"
ASSESSED_AT = "2026-04-04T11:00:00+00:00"
ALLOCATED_AT = "2026-04-05T12:00:00+00:00"
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
) -> CommercialBillingProfile:
    return build_commercial_billing_profile(
        billing_profile_id=billing_profile_id,
        terms_id=terms_id,
        party_type=BillingPartyType.ORGANIZATION,
        bill_to_name="Acme Capital Ltd",
        bill_to_reference="BILLTO-ACME-1",
        seller_reference="SELLER-CSS-1",
        tax_treatment_status=TaxTreatmentStatus.OUT_OF_SCOPE,
        payment_terms_status=PaymentTermsStatus.DEFINED_EXTERNALLY,
        effective_from=PROFILE_FROM,
        evidence_refs=("profile:BP-001",),
        effective_to=PROFILE_TO,
    )


def _candidate(
    *,
    status: InvoiceCandidateStatus = InvoiceCandidateStatus.READY,
    candidate_amount: Decimal = Decimal("1"),
) -> CommercialInvoiceCandidate:
    return build_invoice_candidate(
        _obligation(billable_amount=candidate_amount),
        _profile(),
        status,
        ASSESSED_AT,
        ("candidate:OPS-1",),
    )


def _allocation(
    candidate: CommercialInvoiceCandidate | None = None,
    *,
    invoice_id: str = "INV-ID-001",
    allocated_at: str = ALLOCATED_AT,
    evidence_refs: tuple[str, ...] = ("identity:OPS-1",),
    invoice_number: str | None = None,
) -> CommercialInvoiceIdentityAllocation:
    return build_invoice_identity_allocation(
        candidate if candidate is not None else _candidate(),
        invoice_id=invoice_id,
        allocated_at=allocated_at,
        evidence_refs=evidence_refs,
        invoice_number=invoice_number,
    )


def _assert_all_safety_false(
    allocation: CommercialInvoiceIdentityAllocation,
) -> None:
    assert allocation.invoice_issuance_allowed is False
    assert allocation.invoice_number_generation_allowed is False
    assert allocation.receivable_recognition_allowed is False
    assert allocation.ledger_posting_allowed is False
    assert allocation.revenue_recognition_allowed is False
    assert allocation.tax_calculation_allowed is False
    assert allocation.due_balance_creation_allowed is False
    assert allocation.real_fee_collection_allowed is False
    assert allocation.client_funds_deduction_allowed is False
    assert allocation.automatic_debit_allowed is False
    assert allocation.invoice_settlement_allowed is False
    assert allocation.payment_initiation_allowed is False
    assert allocation.money_movement_allowed is False
    assert allocation.broker_withdrawal_allowed is False
    assert allocation.execution_authority is False


def test_valid_allocation_from_ready_candidate():
    candidate = _candidate()
    allocation = _allocation(candidate)

    assert allocation.invoice_id == "INV-ID-001"
    assert allocation.policy_id == candidate.policy_id
    assert allocation.terms_id == candidate.terms_id
    assert allocation.billing_profile_id == candidate.billing_profile_id
    assert allocation.currency == candidate.currency
    assert allocation.period_start == candidate.period_start
    assert allocation.period_end == candidate.period_end
    assert allocation.invoice_amount == candidate.candidate_amount
    assert allocation.allocated_at == ALLOCATED_AT
    assert allocation.evidence_refs == ("identity:OPS-1",)
    assert allocation.invoice_number is None
    _assert_all_safety_false(allocation)


def test_valid_allocation_with_invoice_number_none():
    allocation = _allocation(invoice_number=None)
    assert allocation.invoice_number is None
    _assert_all_safety_false(allocation)


def test_valid_allocation_with_explicit_invoice_number():
    allocation = _allocation(invoice_number="INV-2026-0001")
    assert allocation.invoice_number == "INV-2026-0001"
    _assert_all_safety_false(allocation)


@pytest.mark.parametrize(
    "status",
    [
        InvoiceCandidateStatus.NOT_READY,
        InvoiceCandidateStatus.BLOCKED,
        InvoiceCandidateStatus.EXPIRED,
    ],
)
def test_allocation_rejected_from_non_ready_candidate(status):
    with pytest.raises(
        InvoiceIdentityIneligibleError,
        match="READY invoice candidate",
    ):
        _allocation(_candidate(status=status))


def test_invoice_amount_copied_exactly():
    candidate = _candidate(candidate_amount=Decimal("1"))
    allocation = _allocation(candidate)
    assert allocation.invoice_amount == Decimal("1")
    assert allocation.invoice_amount is not Decimal("3")
    assert allocation.invoice_amount != Decimal("3")
    assert allocation.invoice_amount != Decimal("5")
    assert allocation.invoice_amount != Decimal("15")


def test_decimal_representation_preserved():
    amount = Decimal("1.2500")
    candidate = _candidate(candidate_amount=amount)
    allocation = _allocation(candidate)
    assert allocation.invoice_amount == amount
    assert format(allocation.invoice_amount, "f") == "1.2500"


def test_zero_amount_supported():
    candidate = _candidate(candidate_amount=Decimal("0"))
    allocation = _allocation(candidate)
    assert allocation.invoice_amount == Decimal("0")


def test_no_economic_recalculation():
    candidate = _candidate(candidate_amount=Decimal("1"))
    allocation = _allocation(candidate)
    assert allocation.invoice_amount == candidate.candidate_amount
    assert allocation.invoice_amount == Decimal("1")


def test_blank_invoice_id_rejected():
    with pytest.raises(ValueError, match="invoice_id"):
        _allocation(invoice_id=" ")


def test_blank_invoice_number_rejected_when_provided():
    with pytest.raises(ValueError, match="invoice_number"):
        _allocation(invoice_number=" ")


def test_blank_policy_id_rejected_direct_construction():
    with pytest.raises(ValueError, match="policy_id"):
        CommercialInvoiceIdentityAllocation(
            invoice_id="INV-ID-001",
            policy_id=" ",
            terms_id="TERMS-001",
            billing_profile_id="BP-001",
            currency="CAD",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            invoice_amount=Decimal("1"),
            allocated_at=ALLOCATED_AT,
            evidence_refs=("identity:OPS-1",),
        )


def test_blank_terms_id_rejected():
    with pytest.raises(ValueError, match="terms_id"):
        CommercialInvoiceIdentityAllocation(
            invoice_id="INV-ID-001",
            policy_id="POLICY-001",
            terms_id="",
            billing_profile_id="BP-001",
            currency="CAD",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            invoice_amount=Decimal("1"),
            allocated_at=ALLOCATED_AT,
            evidence_refs=("identity:OPS-1",),
        )


def test_blank_billing_profile_id_rejected():
    with pytest.raises(ValueError, match="billing_profile_id"):
        CommercialInvoiceIdentityAllocation(
            invoice_id="INV-ID-001",
            policy_id="POLICY-001",
            terms_id="TERMS-001",
            billing_profile_id=" ",
            currency="CAD",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            invoice_amount=Decimal("1"),
            allocated_at=ALLOCATED_AT,
            evidence_refs=("identity:OPS-1",),
        )


def test_lowercase_currency_rejected():
    with pytest.raises(ValueError, match="currency"):
        CommercialInvoiceIdentityAllocation(
            invoice_id="INV-ID-001",
            policy_id="POLICY-001",
            terms_id="TERMS-001",
            billing_profile_id="BP-001",
            currency="cad",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            invoice_amount=Decimal("1"),
            allocated_at=ALLOCATED_AT,
            evidence_refs=("identity:OPS-1",),
        )


def test_invalid_naive_allocated_at_rejected():
    with pytest.raises(ValueError, match="allocated_at"):
        _allocation(allocated_at="2026-04-05T12:00:00")


def test_non_utc_allocated_at_rejected():
    with pytest.raises(ValueError, match="UTC"):
        _allocation(allocated_at="2026-04-05T12:00:00-04:00")


def test_invalid_period_ordering_rejected():
    with pytest.raises(ValueError, match="period_end"):
        CommercialInvoiceIdentityAllocation(
            invoice_id="INV-ID-001",
            policy_id="POLICY-001",
            terms_id="TERMS-001",
            billing_profile_id="BP-001",
            currency="CAD",
            period_start=PERIOD_END,
            period_end=PERIOD_START,
            invoice_amount=Decimal("1"),
            allocated_at=ALLOCATED_AT,
            evidence_refs=("identity:OPS-1",),
        )


def test_missing_evidence_rejected():
    with pytest.raises(ValueError, match="evidence_refs"):
        _allocation(evidence_refs=())


def test_blank_evidence_ref_rejected():
    with pytest.raises(ValueError, match="evidence"):
        _allocation(evidence_refs=(" ",))


def test_object_immutable():
    allocation = _allocation()
    with pytest.raises(FrozenInstanceError):
        allocation.invoice_id = "OTHER"  # type: ignore[misc]


def test_z_suffix_allocated_at_accepted():
    allocation = _allocation(allocated_at="2026-04-05T12:00:00Z")
    assert allocation.allocated_at == "2026-04-05T12:00:00Z"
