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
    build_receivable_recognition,
)
from backend.commercialization.receivable_reversal import (
    CommercialReceivableReversalRecord,
    ReceivableReversalIneligibleError,
    build_receivable_reversal,
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
REVERSED_AT = "2026-04-09T16:00:00+00:00"
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


def _receivable(
    *,
    invoice_id: str = "INV-A",
    receivable_id: str = "REC-A",
    amount: Decimal = Decimal("1"),
) -> CommercialReceivableRecognitionRecord:
    issued = _issued(invoice_id=invoice_id, amount=amount)
    return build_receivable_recognition(
        issued,
        receivable_id=receivable_id,
        recognized_at=RECEIVABLE_AT,
        evidence_refs=("receivable:OPS-1",),
        corrections=(),
    )


def _void_correction(issued: CommercialInvoiceIssuedRecord):
    return build_invoice_correction(
        issued,
        correction_id="COR-A",
        correction_type=InvoiceCorrectionType.VOID,
        corrected_at=CORRECTED_AT,
        reason_reference="reason:VOID-1",
        evidence_refs=("correction:OPS-1",),
    )


def _supersede_correction(
    issued: CommercialInvoiceIssuedRecord,
    replacement: CommercialInvoiceIssuedRecord,
):
    return build_invoice_correction(
        issued,
        correction_id="COR-S",
        correction_type=InvoiceCorrectionType.SUPERSEDE,
        corrected_at=CORRECTED_AT,
        reason_reference="reason:SUPERSEDE-1",
        evidence_refs=("correction:OPS-2",),
        replacement_invoice=replacement,
    )


def _assert_all_safety_false(
    record: CommercialReceivableReversalRecord,
) -> None:
    assert record.receivable_mutation_allowed is False
    assert record.partial_adjustment_allowed is False
    assert record.credit_note_creation_allowed is False
    assert record.writeoff_allowed is False
    assert record.ledger_reversal_allowed is False
    assert record.revenue_reversal_posting_allowed is False
    assert record.outstanding_balance_mutation_allowed is False
    assert record.payment_allocation_allowed is False
    assert record.refund_allowed is False
    assert record.real_fee_collection_allowed is False
    assert record.client_funds_deduction_allowed is False
    assert record.automatic_debit_allowed is False
    assert record.payment_initiation_allowed is False
    assert record.money_movement_allowed is False
    assert record.replacement_receivable_creation_allowed is False
    assert record.broker_withdrawal_allowed is False
    assert record.execution_authority is False


def test_valid_void_triggered_reversal():
    issued = _issued(invoice_id="INV-A", amount=Decimal("25.00"))
    receivable = build_receivable_recognition(
        issued,
        receivable_id="REC-A",
        recognized_at=RECEIVABLE_AT,
        evidence_refs=("receivable:OPS-1",),
        corrections=(),
    )
    correction = _void_correction(issued)
    reversal = build_receivable_reversal(
        receivable,
        correction,
        reversal_id="REV-001",
        reversed_at=REVERSED_AT,
        reason_reference="reason:REV-1",
        evidence_refs=("reversal:OPS-1",),
    )

    assert reversal.receivable_id == "REC-A"
    assert reversal.invoice_id == "INV-A"
    assert reversal.correction_id == "COR-A"
    assert reversal.currency == "CAD"
    assert reversal.reversal_amount == Decimal("25.00")
    assert reversal.reversal_amount != Decimal("-25.00")
    _assert_all_safety_false(reversal)


def test_valid_supersede_triggered_reversal():
    issued = _issued(invoice_id="INV-A", amount=Decimal("25.00"))
    replacement = _issued(
        invoice_id="INV-B",
        period_start=PERIOD_START_2,
        period_end=PERIOD_END_2,
        amount=Decimal("30.00"),
    )
    receivable = build_receivable_recognition(
        issued,
        receivable_id="REC-A",
        recognized_at=RECEIVABLE_AT,
        evidence_refs=("receivable:OPS-1",),
        corrections=(),
    )
    correction = _supersede_correction(issued, replacement)
    reversal = build_receivable_reversal(
        receivable,
        correction,
        reversal_id="REV-002",
        reversed_at=REVERSED_AT,
        reason_reference="reason:REV-2",
        evidence_refs=("reversal:OPS-2",),
    )

    assert reversal.invoice_id == "INV-A"
    assert reversal.receivable_id == "REC-A"
    assert reversal.correction_id == "COR-S"
    assert reversal.reversal_amount == Decimal("25.00")
    assert reversal.replacement_receivable_creation_allowed is False
    _assert_all_safety_false(reversal)


def test_reversal_id_preserved_exactly():
    receivable = _receivable()
    issued = _issued()
    correction = _void_correction(issued)
    reversal = build_receivable_reversal(
        receivable,
        correction,
        reversal_id="REV-OPAQUE-9",
        reversed_at=REVERSED_AT,
        reason_reference="reason:REV-1",
        evidence_refs=("reversal:OPS-1",),
    )
    assert reversal.reversal_id == "REV-OPAQUE-9"


def test_receivable_id_copied_exactly():
    receivable = _receivable(receivable_id="REC-A")
    correction = _void_correction(_issued())
    reversal = build_receivable_reversal(
        receivable,
        correction,
        reversal_id="REV-001",
        reversed_at=REVERSED_AT,
        reason_reference="reason:REV-1",
        evidence_refs=("reversal:OPS-1",),
    )
    assert reversal.receivable_id == receivable.receivable_id
    assert reversal.receivable_id == "REC-A"


def test_invoice_id_copied_exactly():
    receivable = _receivable(invoice_id="INV-A")
    correction = _void_correction(_issued(invoice_id="INV-A"))
    reversal = build_receivable_reversal(
        receivable,
        correction,
        reversal_id="REV-001",
        reversed_at=REVERSED_AT,
        reason_reference="reason:REV-1",
        evidence_refs=("reversal:OPS-1",),
    )
    assert reversal.invoice_id == "INV-A"


def test_correction_id_copied_exactly():
    issued = _issued()
    receivable = _receivable()
    correction = _void_correction(issued)
    reversal = build_receivable_reversal(
        receivable,
        correction,
        reversal_id="REV-001",
        reversed_at=REVERSED_AT,
        reason_reference="reason:REV-1",
        evidence_refs=("reversal:OPS-1",),
    )
    assert reversal.correction_id == correction.correction_id
    assert reversal.correction_id == "COR-A"


def test_currency_copied_exactly():
    receivable = _receivable()
    correction = _void_correction(_issued())
    reversal = build_receivable_reversal(
        receivable,
        correction,
        reversal_id="REV-001",
        reversed_at=REVERSED_AT,
        reason_reference="reason:REV-1",
        evidence_refs=("reversal:OPS-1",),
    )
    assert reversal.currency == receivable.currency
    assert reversal.currency == "CAD"


def test_reversal_amount_copied_exactly():
    receivable = _receivable(amount=Decimal("25.00"))
    correction = _void_correction(_issued(amount=Decimal("25.00")))
    reversal = build_receivable_reversal(
        receivable,
        correction,
        reversal_id="REV-001",
        reversed_at=REVERSED_AT,
        reason_reference="reason:REV-1",
        evidence_refs=("reversal:OPS-1",),
    )
    assert reversal.reversal_amount == Decimal("25.00")
    assert reversal.reversal_amount == receivable.receivable_amount


def test_zero_amount_supported():
    receivable = _receivable(amount=Decimal("0"))
    correction = _void_correction(_issued(amount=Decimal("0")))
    reversal = build_receivable_reversal(
        receivable,
        correction,
        reversal_id="REV-001",
        reversed_at=REVERSED_AT,
        reason_reference="reason:REV-1",
        evidence_refs=("reversal:OPS-1",),
    )
    assert reversal.reversal_amount == Decimal("0")


def test_decimal_representation_preserved():
    receivable = _receivable(amount=Decimal("1.2500"))
    correction = _void_correction(_issued(amount=Decimal("1.2500")))
    reversal = build_receivable_reversal(
        receivable,
        correction,
        reversal_id="REV-001",
        reversed_at=REVERSED_AT,
        reason_reference="reason:REV-1",
        evidence_refs=("reversal:OPS-1",),
    )
    assert reversal.reversal_amount == Decimal("1.2500")
    assert format(reversal.reversal_amount, "f") == "1.2500"


def test_no_negative_sign_transformation():
    receivable = _receivable(amount=Decimal("25.00"))
    correction = _void_correction(_issued(amount=Decimal("25.00")))
    reversal = build_receivable_reversal(
        receivable,
        correction,
        reversal_id="REV-001",
        reversed_at=REVERSED_AT,
        reason_reference="reason:REV-1",
        evidence_refs=("reversal:OPS-1",),
    )
    assert reversal.reversal_amount == Decimal("25.00")
    assert reversal.reversal_amount > Decimal("0")
    assert reversal.reversal_amount != Decimal("-25.00")


def test_invoice_mismatch_rejected():
    receivable = _receivable(invoice_id="INV-A")
    other = _issued(
        invoice_id="INV-B",
        period_start=PERIOD_START_2,
        period_end=PERIOD_END_2,
    )
    correction = _void_correction(other)
    with pytest.raises(
        ReceivableReversalIneligibleError,
        match="invoice_id",
    ):
        build_receivable_reversal(
            receivable,
            correction,
            reversal_id="REV-001",
            reversed_at=REVERSED_AT,
            reason_reference="reason:REV-1",
            evidence_refs=("reversal:OPS-1",),
        )


def test_non_void_supersede_correction_not_constructible():
    # Stage 1 invoice corrections only expose VOID/SUPERSEDE.
    names = {member.name for member in InvoiceCorrectionType}
    assert names == {"VOID", "SUPERSEDE"}
    assert "CREDIT" not in names

    receivable = _receivable()
    with pytest.raises(TypeError, match="CommercialInvoiceCorrectionRecord"):
        build_receivable_reversal(
            receivable,
            object(),  # type: ignore[arg-type]
            reversal_id="REV-001",
            reversed_at=REVERSED_AT,
            reason_reference="reason:REV-1",
            evidence_refs=("reversal:OPS-1",),
        )


def test_blank_reversal_id_rejected():
    receivable = _receivable()
    correction = _void_correction(_issued())
    with pytest.raises(ValueError, match="reversal_id"):
        build_receivable_reversal(
            receivable,
            correction,
            reversal_id=" ",
            reversed_at=REVERSED_AT,
            reason_reference="reason:REV-1",
            evidence_refs=("reversal:OPS-1",),
        )


def test_blank_receivable_id_rejected_direct_construction():
    with pytest.raises(ValueError, match="receivable_id"):
        CommercialReceivableReversalRecord(
            reversal_id="REV-001",
            receivable_id="",
            invoice_id="INV-A",
            correction_id="COR-A",
            currency="CAD",
            reversal_amount=Decimal("1"),
            reversed_at=REVERSED_AT,
            reason_reference="reason:REV-1",
            evidence_refs=("reversal:OPS-1",),
        )


def test_blank_invoice_id_rejected_direct_construction():
    with pytest.raises(ValueError, match="invoice_id"):
        CommercialReceivableReversalRecord(
            reversal_id="REV-001",
            receivable_id="REC-A",
            invoice_id=" ",
            correction_id="COR-A",
            currency="CAD",
            reversal_amount=Decimal("1"),
            reversed_at=REVERSED_AT,
            reason_reference="reason:REV-1",
            evidence_refs=("reversal:OPS-1",),
        )


def test_blank_correction_id_rejected_direct_construction():
    with pytest.raises(ValueError, match="correction_id"):
        CommercialReceivableReversalRecord(
            reversal_id="REV-001",
            receivable_id="REC-A",
            invoice_id="INV-A",
            correction_id="",
            currency="CAD",
            reversal_amount=Decimal("1"),
            reversed_at=REVERSED_AT,
            reason_reference="reason:REV-1",
            evidence_refs=("reversal:OPS-1",),
        )


def test_lowercase_currency_rejected():
    with pytest.raises(ValueError, match="currency"):
        CommercialReceivableReversalRecord(
            reversal_id="REV-001",
            receivable_id="REC-A",
            invoice_id="INV-A",
            correction_id="COR-A",
            currency="cad",
            reversal_amount=Decimal("1"),
            reversed_at=REVERSED_AT,
            reason_reference="reason:REV-1",
            evidence_refs=("reversal:OPS-1",),
        )


def test_naive_reversed_at_rejected():
    receivable = _receivable()
    correction = _void_correction(_issued())
    with pytest.raises(ValueError, match="reversed_at"):
        build_receivable_reversal(
            receivable,
            correction,
            reversal_id="REV-001",
            reversed_at="2026-04-09T16:00:00",
            reason_reference="reason:REV-1",
            evidence_refs=("reversal:OPS-1",),
        )


def test_non_utc_reversed_at_rejected():
    receivable = _receivable()
    correction = _void_correction(_issued())
    with pytest.raises(ValueError, match="UTC"):
        build_receivable_reversal(
            receivable,
            correction,
            reversal_id="REV-001",
            reversed_at="2026-04-09T16:00:00-04:00",
            reason_reference="reason:REV-1",
            evidence_refs=("reversal:OPS-1",),
        )


def test_blank_reason_reference_rejected():
    receivable = _receivable()
    correction = _void_correction(_issued())
    with pytest.raises(ValueError, match="reason_reference"):
        build_receivable_reversal(
            receivable,
            correction,
            reversal_id="REV-001",
            reversed_at=REVERSED_AT,
            reason_reference=" ",
            evidence_refs=("reversal:OPS-1",),
        )


def test_missing_evidence_rejected():
    receivable = _receivable()
    correction = _void_correction(_issued())
    with pytest.raises(ValueError, match="evidence_refs"):
        build_receivable_reversal(
            receivable,
            correction,
            reversal_id="REV-001",
            reversed_at=REVERSED_AT,
            reason_reference="reason:REV-1",
            evidence_refs=(),
        )


def test_blank_evidence_entry_rejected():
    receivable = _receivable()
    correction = _void_correction(_issued())
    with pytest.raises(ValueError, match="evidence"):
        build_receivable_reversal(
            receivable,
            correction,
            reversal_id="REV-001",
            reversed_at=REVERSED_AT,
            reason_reference="reason:REV-1",
            evidence_refs=(" ",),
        )


def test_object_immutable():
    receivable = _receivable()
    correction = _void_correction(_issued())
    reversal = build_receivable_reversal(
        receivable,
        correction,
        reversal_id="REV-001",
        reversed_at=REVERSED_AT,
        reason_reference="reason:REV-1",
        evidence_refs=("reversal:OPS-1",),
    )
    with pytest.raises(FrozenInstanceError):
        reversal.reversal_id = "OTHER"  # type: ignore[misc]


def test_no_partial_adjustment_fields():
    names = {
        field.name for field in fields(CommercialReceivableReversalRecord)
    }
    forbidden = {
        "adjustment_amount",
        "partial_amount",
        "remaining_amount",
        "net_amount",
        "outstanding_amount",
    }
    assert names.isdisjoint(forbidden)


def test_no_balance_fields():
    names = {
        field.name for field in fields(CommercialReceivableReversalRecord)
    }
    forbidden = {
        "outstanding_amount",
        "amount_paid",
        "balance_due",
        "net_amount",
    }
    assert names.isdisjoint(forbidden)


def test_no_gl_fields():
    names = {
        field.name for field in fields(CommercialReceivableReversalRecord)
    }
    forbidden = {
        "journal_id",
        "ar_account",
        "revenue_account",
        "debit_account",
        "credit_account",
        "posting_status",
    }
    assert names.isdisjoint(forbidden)


def test_no_payment_refund_fields():
    names = {
        field.name for field in fields(CommercialReceivableReversalRecord)
    }
    forbidden = {
        "refund_amount",
        "payment_status",
        "payment_allocation",
        "collection_status",
        "credit_note_id",
        "writeoff_amount",
    }
    assert names.isdisjoint(forbidden)


def test_safety_properties_all_false():
    receivable = _receivable()
    correction = _void_correction(_issued())
    reversal = build_receivable_reversal(
        receivable,
        correction,
        reversal_id="REV-001",
        reversed_at=REVERSED_AT,
        reason_reference="reason:REV-1",
        evidence_refs=("reversal:OPS-1",),
    )
    _assert_all_safety_false(reversal)


def test_supersede_does_not_create_replacement_receivable():
    issued = _issued(invoice_id="INV-A")
    replacement = _issued(
        invoice_id="INV-B",
        period_start=PERIOD_START_2,
        period_end=PERIOD_END_2,
    )
    receivable = build_receivable_recognition(
        issued,
        receivable_id="REC-A",
        recognized_at=RECEIVABLE_AT,
        evidence_refs=("receivable:OPS-1",),
        corrections=(),
    )
    correction = _supersede_correction(issued, replacement)
    reversal = build_receivable_reversal(
        receivable,
        correction,
        reversal_id="REV-002",
        reversed_at=REVERSED_AT,
        reason_reference="reason:REV-2",
        evidence_refs=("reversal:OPS-2",),
    )
    assert reversal.invoice_id == "INV-A"
    assert reversal.replacement_receivable_creation_allowed is False
    assert issued.invoice_id == "INV-A"
    assert replacement.invoice_id == "INV-B"
