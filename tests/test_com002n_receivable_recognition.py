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
from backend.commercialization.receivable_recognition import (
    CommercialReceivableRecognitionRecord,
    ReceivableRecognitionIneligibleError,
    build_receivable_recognition,
)


PERIOD_START = "2026-03-01T00:00:00+00:00"
PERIOD_END = "2026-04-01T00:00:00+00:00"
PERIOD_START_2 = "2026-05-01T00:00:00+00:00"
PERIOD_END_2 = "2026-06-01T00:00:00+00:00"
RECOGNIZED_AT = "2026-04-03T10:00:00+00:00"
ASSESSED_AT = "2026-04-04T11:00:00+00:00"
ALLOCATED_AT = "2026-04-05T12:00:00+00:00"
ISSUED_AT = "2026-04-06T13:00:00+00:00"
CORRECTED_AT = "2026-04-07T14:00:00+00:00"
RECEIVABLE_AT = "2026-04-08T15:00:00+00:00"
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
    amount: Decimal = Decimal("1"),
) -> CommercialInvoiceIssuedRecord:
    obligation = CommercialBillableObligation(
        policy_id="POLICY-001",
        terms_id="TERMS-001",
        currency="CAD",
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
        allocated_at=ALLOCATED_AT,
        evidence_refs=("identity:OPS-1",),
    )
    return build_invoice_issued_record(
        allocation,
        issued_at=ISSUED_AT,
        evidence_refs=("issued:OPS-1",),
    )


def _recognize(
    issued: CommercialInvoiceIssuedRecord | None = None,
    *,
    receivable_id: str = "RECV-001",
    recognized_at: str = RECEIVABLE_AT,
    evidence_refs: tuple[str, ...] = ("receivable:OPS-1",),
    corrections: tuple = (),
) -> CommercialReceivableRecognitionRecord:
    return build_receivable_recognition(
        issued if issued is not None else _issued(),
        receivable_id=receivable_id,
        recognized_at=recognized_at,
        evidence_refs=evidence_refs,
        corrections=corrections,
    )


def _assert_all_safety_false(
    record: CommercialReceivableRecognitionRecord,
) -> None:
    assert record.ledger_posting_allowed is False
    assert record.revenue_recognition_posting_allowed is False
    assert record.due_balance_creation_allowed is False
    assert record.outstanding_balance_tracking_allowed is False
    assert record.payment_allocation_allowed is False
    assert record.credit_note_creation_allowed is False
    assert record.receivable_adjustment_allowed is False
    assert record.writeoff_allowed is False
    assert record.real_fee_collection_allowed is False
    assert record.client_funds_deduction_allowed is False
    assert record.automatic_debit_allowed is False
    assert record.payment_initiation_allowed is False
    assert record.money_movement_allowed is False
    assert record.broker_withdrawal_allowed is False
    assert record.execution_authority is False
    assert record.post_recognition_correction_handling_allowed is False


def test_valid_recognition_with_no_corrections():
    issued = _issued(invoice_id="INV-A", amount=Decimal("1.00"))
    record = _recognize(issued)

    assert record.receivable_id == "RECV-001"
    assert record.invoice_id == "INV-A"
    assert record.billing_profile_id == "BP-001"
    assert record.currency == "CAD"
    assert record.receivable_amount == Decimal("1.00")
    assert record.recognized_at == RECEIVABLE_AT
    _assert_all_safety_false(record)


def test_receivable_id_stored_exactly():
    record = _recognize(receivable_id="RECV-OPAQUE-9")
    assert record.receivable_id == "RECV-OPAQUE-9"


def test_invoice_id_copied_exactly():
    issued = _issued(invoice_id="INV-A")
    record = _recognize(issued)
    assert record.invoice_id == issued.invoice_id
    assert record.invoice_id == "INV-A"


def test_billing_profile_id_copied_exactly():
    issued = _issued()
    record = _recognize(issued)
    assert record.billing_profile_id == issued.billing_profile_id
    assert record.billing_profile_id == "BP-001"


def test_currency_copied_exactly():
    issued = _issued()
    record = _recognize(issued)
    assert record.currency == issued.currency
    assert record.currency == "CAD"


def test_receivable_amount_copied_exactly():
    issued = _issued(amount=Decimal("1.00"))
    record = _recognize(issued)
    assert record.receivable_amount == Decimal("1.00")
    assert record.receivable_amount == issued.invoice_amount
    assert record.receivable_amount != Decimal("3")
    assert record.receivable_amount != Decimal("5")
    assert record.receivable_amount != Decimal("15")


def test_zero_amount_supported():
    issued = _issued(amount=Decimal("0"))
    record = _recognize(issued)
    assert record.receivable_amount == Decimal("0")


def test_decimal_representation_preserved():
    issued = _issued(amount=Decimal("1.2500"))
    record = _recognize(issued)
    assert record.receivable_amount == Decimal("1.2500")
    assert format(record.receivable_amount, "f") == "1.2500"


def test_no_economic_recalculation():
    issued = _issued(amount=Decimal("1.00"))
    record = _recognize(issued)
    assert record.receivable_amount is issued.invoice_amount
    assert record.receivable_amount == Decimal("1.00")


def test_void_correction_blocks_recognition():
    issued = _issued(invoice_id="INV-A")
    void = build_invoice_correction(
        issued,
        correction_id="CORR-001",
        correction_type=InvoiceCorrectionType.VOID,
        corrected_at=CORRECTED_AT,
        reason_reference="reason:VOID-1",
        evidence_refs=("correction:OPS-1",),
    )
    with pytest.raises(
        ReceivableRecognitionIneligibleError,
        match="VOID or SUPERSEDE",
    ):
        _recognize(issued, corrections=(void,))


def test_supersede_correction_blocks_recognition():
    issued = _issued(invoice_id="INV-A")
    replacement = _issued(
        invoice_id="INV-B",
        period_start=PERIOD_START_2,
        period_end=PERIOD_END_2,
    )
    supersede = build_invoice_correction(
        issued,
        correction_id="CORR-002",
        correction_type=InvoiceCorrectionType.SUPERSEDE,
        corrected_at=CORRECTED_AT,
        reason_reference="reason:SUPERSEDE-1",
        evidence_refs=("correction:OPS-2",),
        replacement_invoice=replacement,
    )
    with pytest.raises(
        ReceivableRecognitionIneligibleError,
        match="VOID or SUPERSEDE",
    ):
        _recognize(issued, corrections=(supersede,))


def test_correction_for_different_invoice_rejects_snapshot():
    issued = _issued(invoice_id="INV-A")
    other = _issued(
        invoice_id="INV-B",
        period_start=PERIOD_START_2,
        period_end=PERIOD_END_2,
    )
    other_void = build_invoice_correction(
        other,
        correction_id="CORR-OTHER",
        correction_type=InvoiceCorrectionType.VOID,
        corrected_at=CORRECTED_AT,
        reason_reference="reason:VOID-OTHER",
        evidence_refs=("correction:OPS-X",),
    )
    with pytest.raises(
        ReceivableRecognitionIneligibleError,
        match="inconsistent",
    ):
        _recognize(issued, corrections=(other_void,))


def test_multiple_corrections_including_void_blocks():
    issued = _issued(invoice_id="INV-A")
    void = build_invoice_correction(
        issued,
        correction_id="CORR-001",
        correction_type=InvoiceCorrectionType.VOID,
        corrected_at=CORRECTED_AT,
        reason_reference="reason:VOID-1",
        evidence_refs=("correction:OPS-1",),
    )
    void2 = build_invoice_correction(
        issued,
        correction_id="CORR-002",
        correction_type=InvoiceCorrectionType.VOID,
        corrected_at="2026-04-07T15:00:00+00:00",
        reason_reference="reason:VOID-2",
        evidence_refs=("correction:OPS-2",),
    )
    with pytest.raises(ReceivableRecognitionIneligibleError):
        _recognize(issued, corrections=(void, void2))


def test_multiple_corrections_including_supersede_blocks():
    issued = _issued(invoice_id="INV-A")
    replacement = _issued(
        invoice_id="INV-B",
        period_start=PERIOD_START_2,
        period_end=PERIOD_END_2,
    )
    supersede = build_invoice_correction(
        issued,
        correction_id="CORR-002",
        correction_type=InvoiceCorrectionType.SUPERSEDE,
        corrected_at=CORRECTED_AT,
        reason_reference="reason:SUPERSEDE-1",
        evidence_refs=("correction:OPS-2",),
        replacement_invoice=replacement,
    )
    with pytest.raises(ReceivableRecognitionIneligibleError):
        _recognize(issued, corrections=(supersede,))


def test_empty_correction_tuple_permits_recognition():
    record = _recognize(corrections=())
    assert record.invoice_id == "INV-A"
    _assert_all_safety_false(record)


def test_blank_receivable_id_rejected():
    with pytest.raises(ValueError, match="receivable_id"):
        _recognize(receivable_id=" ")


def test_blank_invoice_id_rejected_direct_construction():
    with pytest.raises(ValueError, match="invoice_id"):
        CommercialReceivableRecognitionRecord(
            receivable_id="RECV-001",
            invoice_id="",
            billing_profile_id="BP-001",
            currency="CAD",
            receivable_amount=Decimal("1"),
            recognized_at=RECEIVABLE_AT,
            evidence_refs=("receivable:OPS-1",),
        )


def test_blank_billing_profile_id_rejected():
    with pytest.raises(ValueError, match="billing_profile_id"):
        CommercialReceivableRecognitionRecord(
            receivable_id="RECV-001",
            invoice_id="INV-A",
            billing_profile_id=" ",
            currency="CAD",
            receivable_amount=Decimal("1"),
            recognized_at=RECEIVABLE_AT,
            evidence_refs=("receivable:OPS-1",),
        )


def test_lowercase_currency_rejected():
    with pytest.raises(ValueError, match="currency"):
        CommercialReceivableRecognitionRecord(
            receivable_id="RECV-001",
            invoice_id="INV-A",
            billing_profile_id="BP-001",
            currency="cad",
            receivable_amount=Decimal("1"),
            recognized_at=RECEIVABLE_AT,
            evidence_refs=("receivable:OPS-1",),
        )


def test_naive_recognized_at_rejected():
    with pytest.raises(ValueError, match="recognized_at"):
        _recognize(recognized_at="2026-04-08T15:00:00")


def test_non_utc_recognized_at_rejected():
    with pytest.raises(ValueError, match="UTC"):
        _recognize(recognized_at="2026-04-08T15:00:00-04:00")


def test_missing_evidence_rejected():
    with pytest.raises(ValueError, match="evidence_refs"):
        _recognize(evidence_refs=())


def test_blank_evidence_ref_rejected():
    with pytest.raises(ValueError, match="evidence"):
        _recognize(evidence_refs=(" ",))


def test_object_immutable():
    record = _recognize()
    with pytest.raises(FrozenInstanceError):
        record.receivable_id = "OTHER"  # type: ignore[misc]


def test_no_status_field():
    names = {
        field.name
        for field in fields(CommercialReceivableRecognitionRecord)
    }
    assert "status" not in names
    assert "receivable_status" not in names


def test_no_due_outstanding_payment_fields():
    names = {
        field.name
        for field in fields(CommercialReceivableRecognitionRecord)
    }
    forbidden = {
        "due_date",
        "payment_due_date",
        "overdue",
        "net_days",
        "outstanding_amount",
        "paid_amount",
        "credited_amount",
        "writeoff_amount",
        "balance_due",
        "payment_status",
        "collection_status",
    }
    assert names.isdisjoint(forbidden)


def test_no_gl_accounting_fields():
    names = {
        field.name
        for field in fields(CommercialReceivableRecognitionRecord)
    }
    forbidden = {
        "journal_id",
        "ar_account",
        "revenue_account",
        "debit_account",
        "credit_account",
        "posting_status",
        "tax_rate",
        "tax_amount",
        "customer_id",
        "client_id",
        "account_id",
    }
    assert names.isdisjoint(forbidden)


def test_supersede_does_not_auto_recognize_replacement():
    issued = _issued(invoice_id="INV-A")
    replacement = _issued(
        invoice_id="INV-B",
        period_start=PERIOD_START_2,
        period_end=PERIOD_END_2,
    )
    supersede = build_invoice_correction(
        issued,
        correction_id="CORR-002",
        correction_type=InvoiceCorrectionType.SUPERSEDE,
        corrected_at=CORRECTED_AT,
        reason_reference="reason:SUPERSEDE-1",
        evidence_refs=("correction:OPS-2",),
        replacement_invoice=replacement,
    )
    with pytest.raises(ReceivableRecognitionIneligibleError):
        _recognize(issued, corrections=(supersede,))

    # Replacement may be recognized separately by caller.
    replacement_recognition = _recognize(
        replacement,
        receivable_id="RECV-B",
        corrections=(),
    )
    assert replacement_recognition.invoice_id == "INV-B"
    assert replacement_recognition.receivable_id == "RECV-B"
