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
    CommercialInvoiceCorrectionRecord,
    InvoiceCorrectionError,
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


PERIOD_START = "2026-03-01T00:00:00+00:00"
PERIOD_END = "2026-04-01T00:00:00+00:00"
PERIOD_START_2 = "2026-05-01T00:00:00+00:00"
PERIOD_END_2 = "2026-06-01T00:00:00+00:00"
RECOGNIZED_AT = "2026-04-03T10:00:00+00:00"
ASSESSED_AT = "2026-04-04T11:00:00+00:00"
ALLOCATED_AT = "2026-04-05T12:00:00+00:00"
ISSUED_AT = "2026-04-06T13:00:00+00:00"
CORRECTED_AT = "2026-04-07T14:00:00+00:00"
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


def _assert_all_safety_false(
    record: CommercialInvoiceCorrectionRecord,
) -> None:
    assert record.issued_invoice_mutation_allowed is False
    assert record.credit_note_creation_allowed is False
    assert record.receivable_adjustment_allowed is False
    assert record.ledger_reversal_allowed is False
    assert record.revenue_reversal_allowed is False
    assert record.refund_allowed is False
    assert record.payment_initiation_allowed is False
    assert record.money_movement_allowed is False
    assert record.client_funds_deduction_allowed is False
    assert record.automatic_debit_allowed is False
    assert record.broker_withdrawal_allowed is False
    assert record.execution_authority is False
    assert record.replacement_invoice_creation_allowed is False


def test_valid_void_correction():
    issued = _issued(invoice_id="INV-A")
    correction = build_invoice_correction(
        issued,
        correction_id="CORR-001",
        correction_type=InvoiceCorrectionType.VOID,
        corrected_at=CORRECTED_AT,
        reason_reference="reason:VOID-1",
        evidence_refs=("correction:OPS-1",),
    )

    assert correction.correction_id == "CORR-001"
    assert correction.invoice_id == "INV-A"
    assert correction.correction_type is InvoiceCorrectionType.VOID
    assert correction.replacement_invoice_id is None
    assert correction.reason_reference == "reason:VOID-1"
    _assert_all_safety_false(correction)


def test_void_has_replacement_invoice_id_none():
    correction = build_invoice_correction(
        _issued(),
        correction_id="CORR-001",
        correction_type=InvoiceCorrectionType.VOID,
        corrected_at=CORRECTED_AT,
        reason_reference="reason:VOID-1",
        evidence_refs=("correction:OPS-1",),
    )
    assert correction.replacement_invoice_id is None


def test_void_rejects_replacement_invoice():
    with pytest.raises(
        InvoiceCorrectionError,
        match="VOID requires replacement_invoice=None",
    ):
        build_invoice_correction(
            _issued(invoice_id="INV-A"),
            correction_id="CORR-001",
            correction_type=InvoiceCorrectionType.VOID,
            corrected_at=CORRECTED_AT,
            reason_reference="reason:VOID-1",
            evidence_refs=("correction:OPS-1",),
            replacement_invoice=_issued(
                invoice_id="INV-B",
                period_start=PERIOD_START_2,
                period_end=PERIOD_END_2,
            ),
        )


def test_valid_supersede_correction():
    original = _issued(invoice_id="INV-A")
    replacement = _issued(
        invoice_id="INV-B",
        period_start=PERIOD_START_2,
        period_end=PERIOD_END_2,
    )
    correction = build_invoice_correction(
        original,
        correction_id="CORR-002",
        correction_type=InvoiceCorrectionType.SUPERSEDE,
        corrected_at=CORRECTED_AT,
        reason_reference="reason:SUPERSEDE-1",
        evidence_refs=("correction:OPS-2",),
        replacement_invoice=replacement,
    )

    assert correction.invoice_id == "INV-A"
    assert correction.replacement_invoice_id == "INV-B"
    assert (
        correction.correction_type is InvoiceCorrectionType.SUPERSEDE
    )
    _assert_all_safety_false(correction)


def test_supersede_copies_replacement_invoice_id_exactly():
    original = _issued(invoice_id="INV-A")
    replacement = _issued(
        invoice_id="INV-B",
        period_start=PERIOD_START_2,
        period_end=PERIOD_END_2,
    )
    correction = build_invoice_correction(
        original,
        correction_id="CORR-002",
        correction_type=InvoiceCorrectionType.SUPERSEDE,
        corrected_at=CORRECTED_AT,
        reason_reference="reason:SUPERSEDE-1",
        evidence_refs=("correction:OPS-2",),
        replacement_invoice=replacement,
    )
    assert correction.replacement_invoice_id == replacement.invoice_id
    assert correction.replacement_invoice_id == "INV-B"


def test_supersede_rejects_missing_replacement_invoice():
    with pytest.raises(
        InvoiceCorrectionError,
        match="SUPERSEDE requires replacement_invoice",
    ):
        build_invoice_correction(
            _issued(invoice_id="INV-A"),
            correction_id="CORR-002",
            correction_type=InvoiceCorrectionType.SUPERSEDE,
            corrected_at=CORRECTED_AT,
            reason_reference="reason:SUPERSEDE-1",
            evidence_refs=("correction:OPS-2",),
            replacement_invoice=None,
        )


def test_supersede_rejects_replacement_same_as_original():
    original = _issued(invoice_id="INV-A")
    with pytest.raises(
        InvoiceCorrectionError,
        match="must differ from invoice_id",
    ):
        build_invoice_correction(
            original,
            correction_id="CORR-002",
            correction_type=InvoiceCorrectionType.SUPERSEDE,
            corrected_at=CORRECTED_AT,
            reason_reference="reason:SUPERSEDE-1",
            evidence_refs=("correction:OPS-2",),
            replacement_invoice=original,
        )


def test_blank_correction_id_rejected():
    with pytest.raises(ValueError, match="correction_id"):
        build_invoice_correction(
            _issued(),
            correction_id=" ",
            correction_type=InvoiceCorrectionType.VOID,
            corrected_at=CORRECTED_AT,
            reason_reference="reason:VOID-1",
            evidence_refs=("correction:OPS-1",),
        )


def test_blank_invoice_id_rejected_direct_construction():
    with pytest.raises(ValueError, match="invoice_id"):
        CommercialInvoiceCorrectionRecord(
            correction_id="CORR-001",
            invoice_id="",
            correction_type=InvoiceCorrectionType.VOID,
            corrected_at=CORRECTED_AT,
            reason_reference="reason:VOID-1",
            evidence_refs=("correction:OPS-1",),
        )


def test_invalid_correction_type_rejected():
    with pytest.raises(TypeError, match="InvoiceCorrectionType"):
        CommercialInvoiceCorrectionRecord(
            correction_id="CORR-001",
            invoice_id="INV-A",
            correction_type="VOID",  # type: ignore[arg-type]
            corrected_at=CORRECTED_AT,
            reason_reference="reason:VOID-1",
            evidence_refs=("correction:OPS-1",),
        )


def test_naive_corrected_at_rejected():
    with pytest.raises(ValueError, match="corrected_at"):
        build_invoice_correction(
            _issued(),
            correction_id="CORR-001",
            correction_type=InvoiceCorrectionType.VOID,
            corrected_at="2026-04-07T14:00:00",
            reason_reference="reason:VOID-1",
            evidence_refs=("correction:OPS-1",),
        )


def test_non_utc_corrected_at_rejected():
    with pytest.raises(ValueError, match="UTC"):
        build_invoice_correction(
            _issued(),
            correction_id="CORR-001",
            correction_type=InvoiceCorrectionType.VOID,
            corrected_at="2026-04-07T14:00:00-04:00",
            reason_reference="reason:VOID-1",
            evidence_refs=("correction:OPS-1",),
        )


def test_blank_reason_reference_rejected():
    with pytest.raises(ValueError, match="reason_reference"):
        build_invoice_correction(
            _issued(),
            correction_id="CORR-001",
            correction_type=InvoiceCorrectionType.VOID,
            corrected_at=CORRECTED_AT,
            reason_reference=" ",
            evidence_refs=("correction:OPS-1",),
        )


def test_missing_evidence_rejected():
    with pytest.raises(ValueError, match="evidence_refs"):
        build_invoice_correction(
            _issued(),
            correction_id="CORR-001",
            correction_type=InvoiceCorrectionType.VOID,
            corrected_at=CORRECTED_AT,
            reason_reference="reason:VOID-1",
            evidence_refs=(),
        )


def test_blank_evidence_ref_rejected():
    with pytest.raises(ValueError, match="evidence"):
        build_invoice_correction(
            _issued(),
            correction_id="CORR-001",
            correction_type=InvoiceCorrectionType.VOID,
            corrected_at=CORRECTED_AT,
            reason_reference="reason:VOID-1",
            evidence_refs=(" ",),
        )


def test_object_immutable():
    correction = build_invoice_correction(
        _issued(),
        correction_id="CORR-001",
        correction_type=InvoiceCorrectionType.VOID,
        corrected_at=CORRECTED_AT,
        reason_reference="reason:VOID-1",
        evidence_refs=("correction:OPS-1",),
    )
    with pytest.raises(FrozenInstanceError):
        correction.correction_id = "OTHER"  # type: ignore[misc]


def test_no_credit_enum_exists():
    names = {member.name for member in InvoiceCorrectionType}
    assert names == {"VOID", "SUPERSEDE"}
    assert "CREDIT" not in names
    assert "CANCEL" not in names
    assert "REFUND" not in names
    assert "WRITE_OFF" not in names


def test_no_accounting_amount_fields_exist():
    names = {
        field.name for field in fields(CommercialInvoiceCorrectionRecord)
    }
    forbidden = {
        "credit_amount",
        "credit_note_id",
        "refund_amount",
        "receivable_adjustment",
        "revenue_reversal",
        "invoice_amount",
    }
    assert names.isdisjoint(forbidden)


def test_no_mutation_status_fields_exist():
    names = {
        field.name for field in fields(CommercialInvoiceCorrectionRecord)
    }
    forbidden = {
        "status",
        "invoice_status",
        "issued_status",
        "voided",
        "superseded",
    }
    assert names.isdisjoint(forbidden)


def test_issued_invoice_not_mutated_by_correction():
    original = _issued(invoice_id="INV-A", amount=Decimal("1.00"))
    original_amount = original.invoice_amount
    original_id = original.invoice_id

    build_invoice_correction(
        original,
        correction_id="CORR-001",
        correction_type=InvoiceCorrectionType.VOID,
        corrected_at=CORRECTED_AT,
        reason_reference="reason:VOID-1",
        evidence_refs=("correction:OPS-1",),
    )

    assert original.invoice_id == original_id
    assert original.invoice_amount == original_amount
    assert original.invoice_amount == Decimal("1.00")
