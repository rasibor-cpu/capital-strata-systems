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
from backend.commercialization.receivable_due import (
    CommercialReceivableDueRecord,
    ReceivableDueIneligibleError,
    build_receivable_due_record,
)
from backend.commercialization.receivable_recognition import (
    CommercialReceivableRecognitionRecord,
    build_receivable_recognition,
)
from backend.commercialization.receivable_reversal import (
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
DETERMINED_AT = "2026-04-10T17:00:00+00:00"
PROFILE_FROM = "2026-01-01T00:00:00+00:00"
PROFILE_TO = "2026-12-31T00:00:00+00:00"
DUE_DATE = "2026-10-15"


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


def _reversal_for(
    receivable: CommercialReceivableRecognitionRecord,
    *,
    reversal_id: str = "REV-001",
):
    issued = _issued(invoice_id=receivable.invoice_id)
    correction = build_invoice_correction(
        issued,
        correction_id="COR-A",
        correction_type=InvoiceCorrectionType.VOID,
        corrected_at=CORRECTED_AT,
        reason_reference="reason:VOID-1",
        evidence_refs=("correction:OPS-1",),
    )
    return build_receivable_reversal(
        receivable,
        correction,
        reversal_id=reversal_id,
        reversed_at=REVERSED_AT,
        reason_reference="reason:REV-1",
        evidence_refs=("reversal:OPS-1",),
    )


def _assert_all_safety_false(
    record: CommercialReceivableDueRecord,
) -> None:
    assert record.receivable_mutation_allowed is False
    assert record.due_status_mutation_allowed is False
    assert record.overdue_status_creation_allowed is False
    assert record.ageing_state_storage_allowed is False
    assert record.outstanding_balance_creation_allowed is False
    assert record.outstanding_balance_mutation_allowed is False
    assert record.payment_terms_calculation_allowed is False
    assert record.payment_allocation_allowed is False
    assert record.credit_note_creation_allowed is False
    assert record.writeoff_allowed is False
    assert record.ledger_posting_allowed is False
    assert record.revenue_recognition_posting_allowed is False
    assert record.real_fee_collection_allowed is False
    assert record.client_funds_deduction_allowed is False
    assert record.automatic_debit_allowed is False
    assert record.payment_initiation_allowed is False
    assert record.collection_initiation_allowed is False
    assert record.money_movement_allowed is False
    assert record.broker_withdrawal_allowed is False
    assert record.execution_authority is False


def test_valid_due_record():
    receivable = _receivable()
    record = build_receivable_due_record(
        receivable,
        due_record_id="DUE-A",
        due_date=DUE_DATE,
        determined_at=DETERMINED_AT,
        terms_reference="TERMS-EXT-001",
        evidence_refs=("due:OPS-1",),
    )

    assert record.due_record_id == "DUE-A"
    assert record.receivable_id == "REC-A"
    assert record.invoice_id == "INV-A"
    assert record.due_date == "2026-10-15"
    assert record.determined_at == DETERMINED_AT
    assert record.terms_reference == "TERMS-EXT-001"
    assert record.evidence_refs == ("due:OPS-1",)
    _assert_all_safety_false(record)


def test_due_record_id_preserved_exactly():
    record = build_receivable_due_record(
        _receivable(),
        due_record_id="DUE-OPAQUE-9",
        due_date=DUE_DATE,
        determined_at=DETERMINED_AT,
        terms_reference="TERMS-EXT-001",
        evidence_refs=("due:OPS-1",),
    )
    assert record.due_record_id == "DUE-OPAQUE-9"


def test_receivable_id_copied_exactly():
    receivable = _receivable(receivable_id="REC-A")
    record = build_receivable_due_record(
        receivable,
        due_record_id="DUE-A",
        due_date=DUE_DATE,
        determined_at=DETERMINED_AT,
        terms_reference="TERMS-EXT-001",
        evidence_refs=("due:OPS-1",),
    )
    assert record.receivable_id == receivable.receivable_id
    assert record.receivable_id == "REC-A"


def test_invoice_id_copied_exactly():
    receivable = _receivable(invoice_id="INV-A")
    record = build_receivable_due_record(
        receivable,
        due_record_id="DUE-A",
        due_date=DUE_DATE,
        determined_at=DETERMINED_AT,
        terms_reference="TERMS-EXT-001",
        evidence_refs=("due:OPS-1",),
    )
    assert record.invoice_id == receivable.invoice_id
    assert record.invoice_id == "INV-A"


def test_valid_yyyy_mm_dd_accepted():
    record = build_receivable_due_record(
        _receivable(),
        due_record_id="DUE-A",
        due_date="2026-09-30",
        determined_at=DETERMINED_AT,
        terms_reference="TERMS-EXT-001",
        evidence_refs=("due:OPS-1",),
    )
    assert record.due_date == "2026-09-30"


def test_leap_year_valid_date_accepted():
    record = build_receivable_due_record(
        _receivable(),
        due_record_id="DUE-A",
        due_date="2028-02-29",
        determined_at=DETERMINED_AT,
        terms_reference="TERMS-EXT-001",
        evidence_refs=("due:OPS-1",),
    )
    assert record.due_date == "2028-02-29"


def test_invalid_calendar_date_rejected():
    with pytest.raises(ValueError, match="due_date"):
        build_receivable_due_record(
            _receivable(),
            due_record_id="DUE-A",
            due_date="2026-02-30",
            determined_at=DETERMINED_AT,
            terms_reference="TERMS-EXT-001",
            evidence_refs=("due:OPS-1",),
        )


def test_timestamp_supplied_as_due_date_rejected():
    with pytest.raises(ValueError, match="due_date"):
        build_receivable_due_record(
            _receivable(),
            due_record_id="DUE-A",
            due_date="2026-09-30T00:00:00Z",
            determined_at=DETERMINED_AT,
            terms_reference="TERMS-EXT-001",
            evidence_refs=("due:OPS-1",),
        )


def test_noncanonical_date_format_rejected():
    with pytest.raises(ValueError, match="due_date"):
        build_receivable_due_record(
            _receivable(),
            due_record_id="DUE-A",
            due_date="2026-9-30",
            determined_at=DETERMINED_AT,
            terms_reference="TERMS-EXT-001",
            evidence_refs=("due:OPS-1",),
        )

    with pytest.raises(ValueError, match="due_date"):
        build_receivable_due_record(
            _receivable(),
            due_record_id="DUE-A",
            due_date="09/30/2026",
            determined_at=DETERMINED_AT,
            terms_reference="TERMS-EXT-001",
            evidence_refs=("due:OPS-1",),
        )


def test_blank_due_record_id_rejected():
    with pytest.raises(ValueError, match="due_record_id"):
        build_receivable_due_record(
            _receivable(),
            due_record_id=" ",
            due_date=DUE_DATE,
            determined_at=DETERMINED_AT,
            terms_reference="TERMS-EXT-001",
            evidence_refs=("due:OPS-1",),
        )


def test_blank_receivable_id_rejected_direct_construction():
    with pytest.raises(ValueError, match="receivable_id"):
        CommercialReceivableDueRecord(
            due_record_id="DUE-A",
            receivable_id="",
            invoice_id="INV-A",
            due_date=DUE_DATE,
            determined_at=DETERMINED_AT,
            terms_reference="TERMS-EXT-001",
            evidence_refs=("due:OPS-1",),
        )


def test_blank_invoice_id_rejected_direct_construction():
    with pytest.raises(ValueError, match="invoice_id"):
        CommercialReceivableDueRecord(
            due_record_id="DUE-A",
            receivable_id="REC-A",
            invoice_id=" ",
            due_date=DUE_DATE,
            determined_at=DETERMINED_AT,
            terms_reference="TERMS-EXT-001",
            evidence_refs=("due:OPS-1",),
        )


def test_naive_determined_at_rejected():
    with pytest.raises(ValueError, match="determined_at"):
        build_receivable_due_record(
            _receivable(),
            due_record_id="DUE-A",
            due_date=DUE_DATE,
            determined_at="2026-04-10T17:00:00",
            terms_reference="TERMS-EXT-001",
            evidence_refs=("due:OPS-1",),
        )


def test_non_utc_determined_at_rejected():
    with pytest.raises(ValueError, match="UTC"):
        build_receivable_due_record(
            _receivable(),
            due_record_id="DUE-A",
            due_date=DUE_DATE,
            determined_at="2026-04-10T17:00:00-04:00",
            terms_reference="TERMS-EXT-001",
            evidence_refs=("due:OPS-1",),
        )


def test_blank_terms_reference_rejected():
    with pytest.raises(ValueError, match="terms_reference"):
        build_receivable_due_record(
            _receivable(),
            due_record_id="DUE-A",
            due_date=DUE_DATE,
            determined_at=DETERMINED_AT,
            terms_reference=" ",
            evidence_refs=("due:OPS-1",),
        )


def test_terms_reference_preserved_canonically():
    record = build_receivable_due_record(
        _receivable(),
        due_record_id="DUE-A",
        due_date=DUE_DATE,
        determined_at=DETERMINED_AT,
        terms_reference="TERMS-EXT-001",
        evidence_refs=("due:OPS-1",),
    )
    assert record.terms_reference == "TERMS-EXT-001"
    assert record.terms_reference == record.terms_reference.strip()


def test_missing_evidence_rejected():
    with pytest.raises(ValueError, match="evidence_refs"):
        build_receivable_due_record(
            _receivable(),
            due_record_id="DUE-A",
            due_date=DUE_DATE,
            determined_at=DETERMINED_AT,
            terms_reference="TERMS-EXT-001",
            evidence_refs=(),
        )


def test_blank_evidence_ref_rejected():
    with pytest.raises(ValueError, match="evidence"):
        build_receivable_due_record(
            _receivable(),
            due_record_id="DUE-A",
            due_date=DUE_DATE,
            determined_at=DETERMINED_AT,
            terms_reference="TERMS-EXT-001",
            evidence_refs=("due:OPS-1", " "),
        )


def test_empty_reversal_snapshot_allows_due_record():
    record = build_receivable_due_record(
        _receivable(),
        due_record_id="DUE-A",
        due_date=DUE_DATE,
        determined_at=DETERMINED_AT,
        terms_reference="TERMS-EXT-001",
        evidence_refs=("due:OPS-1",),
        reversals=(),
    )
    assert record.due_record_id == "DUE-A"


def test_existing_reversal_blocks_due_record():
    receivable = _receivable()
    reversal = _reversal_for(receivable)

    with pytest.raises(
        ReceivableDueIneligibleError,
        match="reversal blocks due-date",
    ):
        build_receivable_due_record(
            receivable,
            due_record_id="DUE-A",
            due_date=DUE_DATE,
            determined_at=DETERMINED_AT,
            terms_reference="TERMS-EXT-001",
            evidence_refs=("due:OPS-1",),
            reversals=(reversal,),
        )


def test_unrelated_reversal_in_snapshot_rejected():
    receivable_a = _receivable(
        invoice_id="INV-A",
        receivable_id="REC-A",
    )
    issued_b = _issued(
        invoice_id="INV-B",
        period_start=PERIOD_START_2,
        period_end=PERIOD_END_2,
        amount=Decimal("2"),
    )
    receivable_b = build_receivable_recognition(
        issued_b,
        receivable_id="REC-B",
        recognized_at=RECEIVABLE_AT,
        evidence_refs=("receivable:OPS-2",),
        corrections=(),
    )
    reversal_b = _reversal_for(receivable_b, reversal_id="REV-B")

    with pytest.raises(
        ReceivableDueIneligibleError,
        match="inconsistent",
    ):
        build_receivable_due_record(
            receivable_a,
            due_record_id="DUE-A",
            due_date=DUE_DATE,
            determined_at=DETERMINED_AT,
            terms_reference="TERMS-EXT-001",
            evidence_refs=("due:OPS-1",),
            reversals=(reversal_b,),
        )


def test_object_immutable():
    record = build_receivable_due_record(
        _receivable(),
        due_record_id="DUE-A",
        due_date=DUE_DATE,
        determined_at=DETERMINED_AT,
        terms_reference="TERMS-EXT-001",
        evidence_refs=("due:OPS-1",),
    )
    with pytest.raises(FrozenInstanceError):
        record.due_date = "2026-11-01"  # type: ignore[misc]


def test_no_due_overdue_status_field():
    names = {f.name for f in fields(CommercialReceivableDueRecord)}
    forbidden = {
        "status",
        "due_status",
        "NOT_DUE",
        "DUE",
        "OVERDUE",
        "PAST_DUE",
        "REVERSED",
        "is_due",
        "is_overdue",
    }
    assert names.isdisjoint(forbidden)


def test_no_outstanding_balance_fields():
    names = {f.name for f in fields(CommercialReceivableDueRecord)}
    forbidden = {
        "outstanding_amount",
        "balance_due",
        "amount_due",
        "remaining_amount",
        "amount_paid",
        "amount_credited",
        "amount_written_off",
    }
    assert names.isdisjoint(forbidden)


def test_no_ageing_fields():
    names = {f.name for f in fields(CommercialReceivableDueRecord)}
    forbidden = {
        "days_overdue",
        "days_outstanding",
        "ageing_bucket",
        "aging_bucket",
    }
    assert names.isdisjoint(forbidden)


def test_no_payment_term_calculation_fields():
    names = {f.name for f in fields(CommercialReceivableDueRecord)}
    forbidden = {
        "net_days",
        "grace_days",
        "business_days",
        "holiday_calendar",
        "payment_term_days",
    }
    assert names.isdisjoint(forbidden)


def test_no_gl_fields():
    names = {f.name for f in fields(CommercialReceivableDueRecord)}
    forbidden = {
        "journal_id",
        "ar_account",
        "revenue_account",
        "posting_status",
    }
    assert names.isdisjoint(forbidden)


def test_no_payment_collection_fields():
    names = {f.name for f in fields(CommercialReceivableDueRecord)}
    forbidden = {
        "payment_status",
        "collection_status",
        "payment_method",
        "cash_application",
        "credit_amount",
        "credit_note_id",
        "writeoff_amount",
    }
    assert names.isdisjoint(forbidden)


def test_all_safety_properties_false():
    record = build_receivable_due_record(
        _receivable(),
        due_record_id="DUE-A",
        due_date=DUE_DATE,
        determined_at=DETERMINED_AT,
        terms_reference="TERMS-EXT-001",
        evidence_refs=("due:OPS-1",),
    )
    _assert_all_safety_false(record)
