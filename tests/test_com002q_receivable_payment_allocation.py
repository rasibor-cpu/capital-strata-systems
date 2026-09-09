from dataclasses import FrozenInstanceError, fields
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
    InvoiceCandidateStatus,
    build_invoice_candidate,
)
from backend.commercialization.invoice_identity import (
    build_invoice_identity_allocation,
)
from backend.commercialization.invoice_issued import (
    CommercialInvoiceIssuedRecord,
    build_invoice_issued_record,
)
from backend.commercialization.receivable_payment import (
    CommercialReceivablePaymentRecord,
    build_receivable_payment,
)
from backend.commercialization.receivable_payment_allocation import (
    CommercialReceivablePaymentAllocationRecord,
    ReceivablePaymentAllocationIneligibleError,
    build_receivable_payment_allocation,
)
from backend.commercialization.receivable_recognition import (
    CommercialReceivableRecognitionRecord,
    build_receivable_recognition,
)


PERIOD_START = "2026-03-01T00:00:00+00:00"
PERIOD_END = "2026-04-01T00:00:00+00:00"
PERIOD_START_2 = "2026-05-01T00:00:00+00:00"
PERIOD_END_2 = "2026-06-01T00:00:00+00:00"
RECOGNIZED_AT = "2026-04-03T10:00:00+00:00"
ASSESSED_AT = "2026-04-04T11:00:00+00:00"
IDENTITY_AT = "2026-04-05T12:00:00+00:00"
ISSUED_AT = "2026-04-06T13:00:00+00:00"
RECEIVABLE_AT = "2026-04-08T15:00:00+00:00"
OBSERVED_AT = "2026-04-12T18:00:00+00:00"
ALLOCATED_AT = "2026-04-13T19:00:00+00:00"
PROFILE_FROM = "2026-01-01T00:00:00+00:00"
PROFILE_TO = "2026-12-31T00:00:00+00:00"


def _profile() -> CommercialBillingProfile:
    return build_commercial_billing_profile(
        billing_profile_id="BP-001",
        terms_id="TERMS-001",
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


def _issued(
    *,
    invoice_id: str = "INV-A",
    period_start: str = PERIOD_START,
    period_end: str = PERIOD_END,
    amount: Decimal = Decimal("100.00"),
    currency: str = "CAD",
) -> CommercialInvoiceIssuedRecord:
    obligation = CommercialBillableObligation(
        policy_id="POLICY-001",
        terms_id="TERMS-001",
        currency=currency,
        period_start=period_start,
        period_end=period_end,
        billable_amount=amount,
        recognized_at=RECOGNIZED_AT,
        status=BillableObligationStatus.BILLABLE,
        evidence_refs=("billable:OPS-1",),
    )
    candidate = build_invoice_candidate(
        obligation,
        _profile(),
        InvoiceCandidateStatus.READY,
        ASSESSED_AT,
        ("candidate:OPS-1",),
    )
    allocation = build_invoice_identity_allocation(
        candidate,
        invoice_id=invoice_id,
        allocated_at=IDENTITY_AT,
        evidence_refs=("identity:OPS-1",),
    )
    return build_invoice_issued_record(
        allocation,
        issued_at=ISSUED_AT,
        evidence_refs=("issued:OPS-1",),
    )


def _receivable(
    *,
    invoice_id: str = "INV-A",
    receivable_id: str = "REC-A",
    amount: Decimal = Decimal("100.00"),
    currency: str = "CAD",
    period_start: str = PERIOD_START,
    period_end: str = PERIOD_END,
) -> CommercialReceivableRecognitionRecord:
    issued = _issued(
        invoice_id=invoice_id,
        amount=amount,
        currency=currency,
        period_start=period_start,
        period_end=period_end,
    )
    return build_receivable_recognition(
        issued,
        receivable_id=receivable_id,
        recognized_at=RECEIVABLE_AT,
        evidence_refs=("receivable:OPS-1",),
        corrections=(),
    )


def _payment(
    *,
    payment_id: str = "PAY-1",
    currency: str = "CAD",
    payment_amount: Decimal = Decimal("100.00"),
) -> CommercialReceivablePaymentRecord:
    return build_receivable_payment(
        payment_id=payment_id,
        currency=currency,
        payment_amount=payment_amount,
        observed_at=OBSERVED_AT,
        external_reference="EXT-REF-001",
        evidence_refs=("payment:OPS-1",),
    )


def _allocation(
    payment: CommercialReceivablePaymentRecord | None = None,
    receivable: CommercialReceivableRecognitionRecord | None = None,
    *,
    allocation_id: str = "ALLOC-A",
    allocated_amount: Decimal = Decimal("60.00"),
    allocated_at: str = ALLOCATED_AT,
    evidence_refs: tuple[str, ...] = ("allocation:OPS-1",),
) -> CommercialReceivablePaymentAllocationRecord:
    return build_receivable_payment_allocation(
        payment or _payment(),
        receivable or _receivable(),
        allocation_id=allocation_id,
        allocated_amount=allocated_amount,
        allocated_at=allocated_at,
        evidence_refs=evidence_refs,
    )


def _assert_all_safety_false(
    record: CommercialReceivablePaymentAllocationRecord,
) -> None:
    assert record.payment_execution_allowed is False
    assert record.receivable_mutation_allowed is False
    assert record.outstanding_balance_mutation_allowed is False
    assert record.aggregate_allocation_validation_allowed is False
    assert record.cash_application_authority is False
    assert record.collection_initiation_allowed is False
    assert record.client_funds_deduction_allowed is False
    assert record.automatic_debit_allowed is False
    assert record.ledger_posting_allowed is False
    assert record.cash_posting_allowed is False
    assert record.credit_note_creation_allowed is False
    assert record.writeoff_allowed is False
    assert record.refund_allowed is False
    assert record.money_movement_allowed is False
    assert record.broker_withdrawal_allowed is False
    assert record.execution_authority is False


def test_valid_allocation():
    payment = _payment()
    receivable = _receivable()
    record = _allocation(payment, receivable)

    assert record.allocation_id == "ALLOC-A"
    assert record.payment_id == "PAY-1"
    assert record.receivable_id == "REC-A"
    assert record.invoice_id == "INV-A"
    assert record.currency == "CAD"
    assert record.allocated_amount == Decimal("60.00")
    assert record.allocated_at == ALLOCATED_AT
    assert record.evidence_refs == ("allocation:OPS-1",)
    _assert_all_safety_false(record)


def test_allocation_id_preserved():
    record = _allocation(allocation_id="ALLOC-OPAQUE-9")
    assert record.allocation_id == "ALLOC-OPAQUE-9"


def test_payment_id_copied_exactly():
    payment = _payment(payment_id="PAY-1")
    record = _allocation(payment, _receivable())
    assert record.payment_id == payment.payment_id
    assert record.payment_id == "PAY-1"


def test_receivable_id_copied_exactly():
    receivable = _receivable(receivable_id="REC-A")
    record = _allocation(_payment(), receivable)
    assert record.receivable_id == receivable.receivable_id
    assert record.receivable_id == "REC-A"


def test_invoice_id_copied_exactly():
    receivable = _receivable(invoice_id="INV-A")
    record = _allocation(_payment(), receivable)
    assert record.invoice_id == receivable.invoice_id
    assert record.invoice_id == "INV-A"


def test_currency_copied_exactly():
    payment = _payment(currency="CAD")
    receivable = _receivable(currency="CAD")
    record = _allocation(payment, receivable)
    assert record.currency == payment.currency
    assert record.currency == receivable.currency
    assert record.currency == "CAD"


def test_payment_receivable_currency_mismatch_rejected():
    payment = _payment(currency="CAD")
    receivable = _receivable(currency="USD")

    with pytest.raises(
        ReceivablePaymentAllocationIneligibleError,
        match="currency",
    ):
        _allocation(payment, receivable)


def test_decimal_allocated_amount_exact():
    record = _allocation(
        _payment(payment_amount=Decimal("10.00")),
        allocated_amount=Decimal("3.50"),
    )
    assert record.allocated_amount == Decimal("3.50")


def test_zero_allocation_supported():
    record = _allocation(allocated_amount=Decimal("0"))
    assert record.allocated_amount == Decimal("0")


def test_negative_allocation_rejected():
    with pytest.raises(ValueError, match="allocated_amount"):
        _allocation(allocated_amount=Decimal("-1"))


def test_float_allocation_rejected():
    with pytest.raises(TypeError, match="allocated_amount"):
        build_receivable_payment_allocation(
            _payment(),
            _receivable(),
            allocation_id="ALLOC-A",
            allocated_amount=30.0,  # type: ignore[arg-type]
            allocated_at=ALLOCATED_AT,
            evidence_refs=("allocation:OPS-1",),
        )


def test_allocation_over_payment_rejected():
    payment = _payment(payment_amount=Decimal("30.00"))

    with pytest.raises(
        ReceivablePaymentAllocationIneligibleError,
        match="payment_amount",
    ):
        _allocation(
            payment,
            allocated_amount=Decimal("30.01"),
        )


def test_allocation_equal_payment_accepted():
    payment = _payment(payment_amount=Decimal("30.00"))
    record = _allocation(
        payment,
        allocated_amount=Decimal("30.00"),
    )
    assert record.allocated_amount == Decimal("30.00")


def test_smaller_partial_allocation_accepted():
    payment = _payment(payment_amount=Decimal("100.00"))
    receivable = _receivable(amount=Decimal("100.00"))
    record = _allocation(
        payment,
        receivable,
        allocated_amount=Decimal("30.00"),
    )
    assert record.allocated_amount == Decimal("30.00")
    names = {
        f.name
        for f in fields(CommercialReceivablePaymentAllocationRecord)
    }
    assert "outstanding_amount" not in names


def test_naive_allocated_at_rejected():
    with pytest.raises(ValueError, match="allocated_at"):
        _allocation(allocated_at="2026-04-13T19:00:00")


def test_non_utc_allocated_at_rejected():
    with pytest.raises(ValueError, match="UTC"):
        _allocation(allocated_at="2026-04-13T19:00:00-04:00")


def test_missing_evidence_rejected():
    with pytest.raises(ValueError, match="evidence_refs"):
        _allocation(evidence_refs=())


def test_blank_evidence_rejected():
    with pytest.raises(ValueError, match="evidence"):
        _allocation(evidence_refs=("allocation:OPS-1", " "))


def test_object_immutable():
    record = _allocation()
    with pytest.raises(FrozenInstanceError):
        record.allocated_amount = Decimal("1")  # type: ignore[misc]


def test_no_balance_fields():
    names = {
        f.name
        for f in fields(CommercialReceivablePaymentAllocationRecord)
    }
    forbidden = {
        "outstanding_amount",
        "balance_due",
        "remaining_receivable_amount",
        "remaining_payment_amount",
        "amount_paid_total",
        "remaining_amount",
        "overpayment_status",
    }
    assert names.isdisjoint(forbidden)


def test_no_payment_status():
    names = {
        f.name
        for f in fields(CommercialReceivablePaymentAllocationRecord)
    }
    forbidden = {
        "status",
        "payment_status",
        "allocation_status",
        "PENDING",
        "SETTLED",
        "CLEARED",
        "FAILED",
        "PAID",
        "PARTIALLY_PAID",
        "APPLIED",
        "UNAPPLIED",
    }
    assert names.isdisjoint(forbidden)


def test_no_gl_fields():
    names = {
        f.name
        for f in fields(CommercialReceivablePaymentAllocationRecord)
    }
    forbidden = {
        "journal_id",
        "cash_account",
        "ar_account",
        "revenue_account",
        "posting_status",
        "cash_posted",
        "credit_amount",
        "credit_note_id",
        "writeoff_amount",
        "refund_amount",
    }
    assert names.isdisjoint(forbidden)


def test_no_aggregate_allocation_calculation():
    payment = _payment(payment_amount=Decimal("100.00"))
    receivable_a = _receivable(
        invoice_id="INV-A",
        receivable_id="REC-A",
        amount=Decimal("60.00"),
    )
    receivable_b = _receivable(
        invoice_id="INV-B",
        receivable_id="REC-B",
        amount=Decimal("40.00"),
        period_start=PERIOD_START_2,
        period_end=PERIOD_END_2,
    )

    alloc_a = _allocation(
        payment,
        receivable_a,
        allocation_id="ALLOC-A",
        allocated_amount=Decimal("60.00"),
    )
    alloc_b = _allocation(
        payment,
        receivable_b,
        allocation_id="ALLOC-B",
        allocated_amount=Decimal("40.00"),
    )

    assert alloc_a.payment_id == payment.payment_id
    assert alloc_b.payment_id == payment.payment_id
    assert alloc_a.receivable_id == "REC-A"
    assert alloc_b.receivable_id == "REC-B"
    assert not hasattr(payment, "receivable_id")
    assert not hasattr(payment, "allocations")
    assert not hasattr(
        CommercialReceivablePaymentAllocationRecord,
        "total_allocated",
    )
    assert (
        alloc_a.aggregate_allocation_validation_allowed is False
    )


def test_all_safety_properties_false():
    _assert_all_safety_false(_allocation())


def test_payment_remains_independent_of_receivables():
    payment = _payment(payment_amount=Decimal("100.00"))
    names = {f.name for f in fields(type(payment))}
    assert "receivable_id" not in names
    assert "invoice_id" not in names
