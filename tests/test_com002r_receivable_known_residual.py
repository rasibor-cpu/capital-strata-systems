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
from backend.commercialization.invoice_correction import (
    InvoiceCorrectionType,
    build_invoice_correction,
)
from backend.commercialization.invoice_identity import (
    build_invoice_identity_allocation,
)
from backend.commercialization.invoice_issued import (
    CommercialInvoiceIssuedRecord,
    build_invoice_issued_record,
)
from backend.commercialization.receivable_known_residual import (
    CommercialReceivableKnownResidualProjection,
    ReceivableKnownResidualIneligibleError,
    build_receivable_known_residual_projection,
)
from backend.commercialization.receivable_payment import (
    build_receivable_payment,
)
from backend.commercialization.receivable_payment_allocation import (
    CommercialReceivablePaymentAllocationRecord,
    build_receivable_payment_allocation,
)
from backend.commercialization.receivable_recognition import (
    CommercialReceivableRecognitionRecord,
    build_receivable_recognition,
)
from backend.commercialization.receivable_reversal import (
    CommercialReceivableReversalRecord,
    build_receivable_reversal,
)


PERIOD_START = "2026-03-01T00:00:00+00:00"
PERIOD_END = "2026-04-01T00:00:00+00:00"
PERIOD_START_2 = "2026-05-01T00:00:00+00:00"
PERIOD_END_2 = "2026-06-01T00:00:00+00:00"
RECOGNIZED_AT = "2026-04-03T10:00:00+00:00"
ASSESSED_AT = "2026-04-04T11:00:00+00:00"
IDENTITY_AT = "2026-04-05T12:00:00+00:00"
ISSUED_AT = "2026-04-06T13:00:00+00:00"
CORRECTED_AT = "2026-04-07T14:00:00+00:00"
RECEIVABLE_AT = "2026-04-08T15:00:00+00:00"
REVERSED_AT = "2026-04-09T16:00:00+00:00"
OBSERVED_AT = "2026-04-12T18:00:00+00:00"
ALLOCATED_AT = "2026-04-13T19:00:00+00:00"
AS_OF = "2026-04-15T12:00:00+00:00"
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


def _recognition(
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


def _reversal_for(
    recognition: CommercialReceivableRecognitionRecord,
    *,
    reversal_id: str = "REV-001",
) -> CommercialReceivableReversalRecord:
    issued = _issued(
        invoice_id=recognition.invoice_id,
        amount=recognition.receivable_amount,
        currency=recognition.currency,
    )
    correction = build_invoice_correction(
        issued,
        correction_id="COR-A",
        correction_type=InvoiceCorrectionType.VOID,
        corrected_at=CORRECTED_AT,
        reason_reference="reason:VOID-1",
        evidence_refs=("correction:OPS-1",),
    )
    return build_receivable_reversal(
        recognition,
        correction,
        reversal_id=reversal_id,
        reversed_at=REVERSED_AT,
        reason_reference="reason:REV-1",
        evidence_refs=("reversal:OPS-1",),
    )


def _allocation_for(
    recognition: CommercialReceivableRecognitionRecord,
    *,
    allocation_id: str = "ALLOC-A",
    payment_id: str = "PAY-1",
    payment_amount: Decimal | None = None,
    allocated_amount: Decimal = Decimal("30.00"),
    allocated_at: str = ALLOCATED_AT,
) -> CommercialReceivablePaymentAllocationRecord:
    pay_amount = (
        payment_amount
        if payment_amount is not None
        else allocated_amount
    )
    payment = build_receivable_payment(
        payment_id=payment_id,
        currency=recognition.currency,
        payment_amount=pay_amount,
        observed_at=OBSERVED_AT,
        external_reference=f"EXT-{payment_id}",
        evidence_refs=("payment:OPS-1",),
    )
    return build_receivable_payment_allocation(
        payment,
        recognition,
        allocation_id=allocation_id,
        allocated_amount=allocated_amount,
        allocated_at=allocated_at,
        evidence_refs=("allocation:OPS-1",),
    )


def _assert_all_safety_false(
    projection: CommercialReceivableKnownResidualProjection,
) -> None:
    assert projection.mutable_balance_allowed is False
    assert projection.receivable_mutation_allowed is False
    assert projection.payment_execution_allowed is False
    assert projection.collection_initiation_allowed is False
    assert projection.client_funds_deduction_allowed is False
    assert projection.automatic_debit_allowed is False
    assert projection.ledger_posting_allowed is False
    assert projection.cash_posting_allowed is False
    assert projection.credit_note_creation_allowed is False
    assert projection.writeoff_allowed is False
    assert projection.refund_allowed is False
    assert projection.money_movement_allowed is False
    assert projection.broker_withdrawal_allowed is False
    assert projection.execution_authority is False
    assert projection.complete_balance_claim_allowed is False
    assert projection.overpayment_resolution_allowed is False


def test_recognition_only_projection():
    recognition = _recognition()
    projection = build_receivable_known_residual_projection(
        recognition,
        as_of=AS_OF,
    )

    assert projection.receivable_id == "REC-A"
    assert projection.invoice_id == "INV-A"
    assert projection.currency == "CAD"
    assert projection.as_of == AS_OF
    assert projection.recognized_amount == Decimal("100.00")
    assert projection.reversed_amount == Decimal("0")
    assert projection.allocated_amount == Decimal("0")
    assert projection.residual_amount == Decimal("100.00")
    assert projection.payment_events_included is True
    assert projection.credit_events_supported is False
    assert projection.writeoff_events_supported is False
    assert projection.is_complete_balance is False
    _assert_all_safety_false(projection)


def test_recognized_amount_copied_exactly():
    recognition = _recognition(amount=Decimal("3.50"))
    projection = build_receivable_known_residual_projection(
        recognition,
        as_of=AS_OF,
    )
    assert projection.recognized_amount == Decimal("3.50")
    assert str(projection.recognized_amount) == "3.50"


def test_zero_reversed_amount_without_reversal():
    projection = build_receivable_known_residual_projection(
        _recognition(),
        as_of=AS_OF,
    )
    assert projection.reversed_amount == Decimal("0")


def test_zero_allocated_amount_without_allocations():
    projection = build_receivable_known_residual_projection(
        _recognition(),
        as_of=AS_OF,
        allocations=(),
    )
    assert projection.allocated_amount == Decimal("0")


def test_residual_equals_recognized_with_no_offsets():
    projection = build_receivable_known_residual_projection(
        _recognition(amount=Decimal("100.00")),
        as_of=AS_OF,
    )
    assert projection.residual_amount == Decimal("100.00")


def test_one_allocation_reduces_residual():
    recognition = _recognition()
    allocation = _allocation_for(
        recognition,
        allocated_amount=Decimal("30.00"),
    )
    projection = build_receivable_known_residual_projection(
        recognition,
        as_of=AS_OF,
        allocations=(allocation,),
    )
    assert projection.allocated_amount == Decimal("30.00")
    assert projection.residual_amount == Decimal("70.00")


def test_multiple_allocations_sum_exactly():
    recognition = _recognition()
    alloc_a = _allocation_for(
        recognition,
        allocation_id="ALLOC-A",
        payment_id="PAY-A",
        allocated_amount=Decimal("30.00"),
    )
    alloc_b = _allocation_for(
        recognition,
        allocation_id="ALLOC-B",
        payment_id="PAY-B",
        allocated_amount=Decimal("20.00"),
    )
    projection = build_receivable_known_residual_projection(
        recognition,
        as_of=AS_OF,
        allocations=(alloc_a, alloc_b),
    )
    assert projection.allocated_amount == Decimal("50.00")
    assert projection.residual_amount == Decimal("50.00")
    assert projection.is_complete_balance is False


def test_partial_residual_exact_decimal():
    recognition = _recognition(amount=Decimal("100.00"))
    allocation = _allocation_for(
        recognition,
        allocated_amount=Decimal("33.33"),
    )
    projection = build_receivable_known_residual_projection(
        recognition,
        as_of=AS_OF,
        allocations=(allocation,),
    )
    assert projection.residual_amount == Decimal("66.67")


def test_full_allocation_gives_zero_residual():
    recognition = _recognition(amount=Decimal("100.00"))
    allocation = _allocation_for(
        recognition,
        allocated_amount=Decimal("100.00"),
        payment_amount=Decimal("100.00"),
    )
    projection = build_receivable_known_residual_projection(
        recognition,
        as_of=AS_OF,
        allocations=(allocation,),
    )
    assert projection.residual_amount == Decimal("0")


def test_allocation_aggregate_over_recognized_rejects():
    recognition = _recognition(amount=Decimal("100.00"))
    alloc_a = _allocation_for(
        recognition,
        allocation_id="ALLOC-A",
        payment_id="PAY-A",
        allocated_amount=Decimal("70.00"),
        payment_amount=Decimal("70.00"),
    )
    alloc_b = _allocation_for(
        recognition,
        allocation_id="ALLOC-B",
        payment_id="PAY-B",
        allocated_amount=Decimal("40.00"),
        payment_amount=Decimal("40.00"),
    )
    with pytest.raises(
        ReceivableKnownResidualIneligibleError,
        match="exceeds recognized_amount",
    ):
        build_receivable_known_residual_projection(
            recognition,
            as_of=AS_OF,
            allocations=(alloc_a, alloc_b),
        )


def test_no_clamping_on_over_allocation():
    recognition = _recognition(amount=Decimal("100.00"))
    alloc_a = _allocation_for(
        recognition,
        allocation_id="ALLOC-A",
        payment_id="PAY-A",
        allocated_amount=Decimal("70.00"),
        payment_amount=Decimal("70.00"),
    )
    alloc_b = _allocation_for(
        recognition,
        allocation_id="ALLOC-B",
        payment_id="PAY-B",
        allocated_amount=Decimal("40.00"),
        payment_amount=Decimal("40.00"),
    )
    with pytest.raises(ReceivableKnownResidualIneligibleError):
        build_receivable_known_residual_projection(
            recognition,
            as_of=AS_OF,
            allocations=(alloc_a, alloc_b),
        )


def test_no_negative_residual_returned():
    recognition = _recognition(amount=Decimal("100.00"))
    allocation = _allocation_for(
        recognition,
        allocated_amount=Decimal("40.00"),
        payment_amount=Decimal("40.00"),
    )
    projection = build_receivable_known_residual_projection(
        recognition,
        as_of=AS_OF,
        allocations=(allocation,),
    )
    assert projection.residual_amount >= Decimal("0")


def test_valid_reversal_forces_residual_zero():
    recognition = _recognition()
    reversal = _reversal_for(recognition)
    projection = build_receivable_known_residual_projection(
        recognition,
        as_of=AS_OF,
        reversal=reversal,
    )
    assert projection.residual_amount == Decimal("0")


def test_valid_reversal_copies_full_recognized_into_reversed():
    recognition = _recognition(amount=Decimal("100.00"))
    reversal = _reversal_for(recognition)
    projection = build_receivable_known_residual_projection(
        recognition,
        as_of=AS_OF,
        reversal=reversal,
    )
    assert projection.reversed_amount == Decimal("100.00")
    assert projection.reversed_amount == recognition.receivable_amount


def test_allocations_remain_reported_when_reversal_exists():
    recognition = _recognition()
    reversal = _reversal_for(recognition)
    allocation = _allocation_for(
        recognition,
        allocated_amount=Decimal("30.00"),
    )
    projection = build_receivable_known_residual_projection(
        recognition,
        as_of=AS_OF,
        reversal=reversal,
        allocations=(allocation,),
    )
    assert projection.allocated_amount == Decimal("30.00")


def test_reversed_residual_stays_zero_despite_allocations():
    recognition = _recognition()
    reversal = _reversal_for(recognition)
    allocation = _allocation_for(
        recognition,
        allocated_amount=Decimal("30.00"),
    )
    projection = build_receivable_known_residual_projection(
        recognition,
        as_of=AS_OF,
        reversal=reversal,
        allocations=(allocation,),
    )
    assert projection.residual_amount == Decimal("0")
    assert projection.residual_amount != Decimal("-30.00")


def test_reversal_receivable_mismatch_rejected():
    recognition = _recognition(receivable_id="REC-A")
    other = _recognition(
        invoice_id="INV-B",
        receivable_id="REC-B",
        period_start=PERIOD_START_2,
        period_end=PERIOD_END_2,
    )
    reversal = _reversal_for(other)

    with pytest.raises(
        ReceivableKnownResidualIneligibleError,
        match="receivable_id",
    ):
        build_receivable_known_residual_projection(
            recognition,
            as_of=AS_OF,
            reversal=reversal,
        )


def test_reversal_invoice_mismatch_rejected():
    recognition = _recognition()
    reversal = _reversal_for(recognition)
    mismatched = CommercialReceivableReversalRecord(
        reversal_id=reversal.reversal_id,
        receivable_id=recognition.receivable_id,
        invoice_id="INV-MISMATCH",
        correction_id=reversal.correction_id,
        currency=reversal.currency,
        reversal_amount=reversal.reversal_amount,
        reversed_at=reversal.reversed_at,
        reason_reference=reversal.reason_reference,
        evidence_refs=reversal.evidence_refs,
    )

    with pytest.raises(
        ReceivableKnownResidualIneligibleError,
        match="invoice_id",
    ):
        build_receivable_known_residual_projection(
            recognition,
            as_of=AS_OF,
            reversal=mismatched,
        )


def test_reversal_currency_mismatch_rejected():
    recognition = _recognition(currency="CAD")
    reversal = _reversal_for(recognition)
    mismatched = CommercialReceivableReversalRecord(
        reversal_id=reversal.reversal_id,
        receivable_id=reversal.receivable_id,
        invoice_id=reversal.invoice_id,
        correction_id=reversal.correction_id,
        currency="USD",
        reversal_amount=reversal.reversal_amount,
        reversed_at=reversal.reversed_at,
        reason_reference=reversal.reason_reference,
        evidence_refs=reversal.evidence_refs,
    )

    with pytest.raises(
        ReceivableKnownResidualIneligibleError,
        match="currency",
    ):
        build_receivable_known_residual_projection(
            recognition,
            as_of=AS_OF,
            reversal=mismatched,
        )


def test_reversal_amount_mismatch_rejected():
    recognition = _recognition(amount=Decimal("100.00"))
    reversal = _reversal_for(recognition)
    mismatched = CommercialReceivableReversalRecord(
        reversal_id=reversal.reversal_id,
        receivable_id=reversal.receivable_id,
        invoice_id=reversal.invoice_id,
        correction_id=reversal.correction_id,
        currency=reversal.currency,
        reversal_amount=Decimal("99.00"),
        reversed_at=reversal.reversed_at,
        reason_reference=reversal.reason_reference,
        evidence_refs=reversal.evidence_refs,
    )

    with pytest.raises(
        ReceivableKnownResidualIneligibleError,
        match="reversal_amount",
    ):
        build_receivable_known_residual_projection(
            recognition,
            as_of=AS_OF,
            reversal=mismatched,
        )


def test_allocation_receivable_mismatch_rejected():
    recognition = _recognition(receivable_id="REC-A")
    other = _recognition(
        invoice_id="INV-B",
        receivable_id="REC-B",
        period_start=PERIOD_START_2,
        period_end=PERIOD_END_2,
    )
    allocation = _allocation_for(other)

    with pytest.raises(
        ReceivableKnownResidualIneligibleError,
        match="receivable_id",
    ):
        build_receivable_known_residual_projection(
            recognition,
            as_of=AS_OF,
            allocations=(allocation,),
        )


def test_allocation_invoice_mismatch_rejected():
    recognition = _recognition()
    allocation = _allocation_for(recognition)
    mismatched = CommercialReceivablePaymentAllocationRecord(
        allocation_id=allocation.allocation_id,
        payment_id=allocation.payment_id,
        receivable_id=recognition.receivable_id,
        invoice_id="INV-MISMATCH",
        currency=allocation.currency,
        allocated_amount=allocation.allocated_amount,
        allocated_at=allocation.allocated_at,
        evidence_refs=allocation.evidence_refs,
    )

    with pytest.raises(
        ReceivableKnownResidualIneligibleError,
        match="invoice_id",
    ):
        build_receivable_known_residual_projection(
            recognition,
            as_of=AS_OF,
            allocations=(mismatched,),
        )


def test_allocation_currency_mismatch_rejected():
    recognition = _recognition(currency="CAD")
    allocation = _allocation_for(recognition)
    mismatched = CommercialReceivablePaymentAllocationRecord(
        allocation_id=allocation.allocation_id,
        payment_id=allocation.payment_id,
        receivable_id=allocation.receivable_id,
        invoice_id=allocation.invoice_id,
        currency="USD",
        allocated_amount=allocation.allocated_amount,
        allocated_at=allocation.allocated_at,
        evidence_refs=allocation.evidence_refs,
    )

    with pytest.raises(
        ReceivableKnownResidualIneligibleError,
        match="currency",
    ):
        build_receivable_known_residual_projection(
            recognition,
            as_of=AS_OF,
            allocations=(mismatched,),
        )


def test_duplicate_allocation_id_rejected():
    recognition = _recognition()
    alloc_a = _allocation_for(
        recognition,
        allocation_id="ALLOC-DUP",
        payment_id="PAY-A",
        allocated_amount=Decimal("10.00"),
    )
    alloc_b = _allocation_for(
        recognition,
        allocation_id="ALLOC-DUP",
        payment_id="PAY-B",
        allocated_amount=Decimal("20.00"),
    )

    with pytest.raises(
        ReceivableKnownResidualIneligibleError,
        match="duplicate allocation_id",
    ):
        build_receivable_known_residual_projection(
            recognition,
            as_of=AS_OF,
            allocations=(alloc_a, alloc_b),
        )


def test_empty_allocations_accepted():
    projection = build_receivable_known_residual_projection(
        _recognition(),
        as_of=AS_OF,
        allocations=(),
    )
    assert projection.allocated_amount == Decimal("0")


def test_zero_recognition_supported():
    projection = build_receivable_known_residual_projection(
        _recognition(amount=Decimal("0")),
        as_of=AS_OF,
    )
    assert projection.recognized_amount == Decimal("0")
    assert projection.residual_amount == Decimal("0")


def test_zero_recognition_positive_allocation_rejected():
    recognition = _recognition(amount=Decimal("0"))
    allocation = _allocation_for(
        recognition,
        allocated_amount=Decimal("1.00"),
        payment_amount=Decimal("1.00"),
    )

    with pytest.raises(
        ReceivableKnownResidualIneligibleError,
        match="exceeds recognized_amount",
    ):
        build_receivable_known_residual_projection(
            recognition,
            as_of=AS_OF,
            allocations=(allocation,),
        )


def test_utc_as_of_accepted():
    projection = build_receivable_known_residual_projection(
        _recognition(),
        as_of="2026-04-15T12:00:00Z",
    )
    assert projection.as_of == "2026-04-15T12:00:00Z"


def test_naive_as_of_rejected():
    with pytest.raises(ValueError, match="as_of"):
        build_receivable_known_residual_projection(
            _recognition(),
            as_of="2026-04-15T12:00:00",
        )


def test_non_utc_as_of_rejected():
    with pytest.raises(ValueError, match="UTC"):
        build_receivable_known_residual_projection(
            _recognition(),
            as_of="2026-04-15T12:00:00-04:00",
        )


def test_no_event_time_filtering_performed():
    recognition = _recognition()
    future_allocation = _allocation_for(
        recognition,
        allocated_amount=Decimal("25.00"),
        allocated_at="2026-12-31T23:59:59+00:00",
    )
    projection = build_receivable_known_residual_projection(
        recognition,
        as_of="2026-01-01T00:00:00+00:00",
        allocations=(future_allocation,),
    )
    assert projection.allocated_amount == Decimal("25.00")
    assert projection.residual_amount == Decimal("75.00")


def test_payment_events_included_true():
    projection = build_receivable_known_residual_projection(
        _recognition(),
        as_of=AS_OF,
    )
    assert projection.payment_events_included is True


def test_credit_events_supported_false():
    projection = build_receivable_known_residual_projection(
        _recognition(),
        as_of=AS_OF,
    )
    assert projection.credit_events_supported is False


def test_writeoff_events_supported_false():
    projection = build_receivable_known_residual_projection(
        _recognition(),
        as_of=AS_OF,
    )
    assert projection.writeoff_events_supported is False


def test_is_complete_balance_false():
    projection = build_receivable_known_residual_projection(
        _recognition(),
        as_of=AS_OF,
    )
    assert projection.is_complete_balance is False


def test_object_immutable():
    projection = build_receivable_known_residual_projection(
        _recognition(),
        as_of=AS_OF,
    )
    with pytest.raises(FrozenInstanceError):
        projection.residual_amount = Decimal("1")  # type: ignore[misc]


def test_no_due_overdue_fields():
    names = {
        f.name
        for f in fields(CommercialReceivableKnownResidualProjection)
    }
    forbidden = {
        "due_date",
        "is_due",
        "is_overdue",
        "days_overdue",
        "ageing_bucket",
        "aging_bucket",
    }
    assert names.isdisjoint(forbidden)


def test_no_complete_balance_fields():
    names = {
        f.name
        for f in fields(CommercialReceivableKnownResidualProjection)
    }
    forbidden = {
        "outstanding_amount",
        "open_balance",
        "balance_due",
        "final_balance",
        "collectible_amount",
        "credit_amount",
        "credited_amount",
        "writeoff_amount",
        "written_off_amount",
        "refund_amount",
    }
    assert names.isdisjoint(forbidden)


def test_no_gl_fields():
    names = {
        f.name
        for f in fields(CommercialReceivableKnownResidualProjection)
    }
    forbidden = {
        "journal_id",
        "cash_account",
        "ar_account",
        "revenue_account",
        "posting_status",
        "payment_status",
        "collection_status",
    }
    assert names.isdisjoint(forbidden)


def test_all_safety_properties_false():
    _assert_all_safety_false(
        build_receivable_known_residual_projection(
            _recognition(),
            as_of=AS_OF,
        )
    )
