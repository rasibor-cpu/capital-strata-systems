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
from backend.commercialization.receivable_recognition import (
    CommercialReceivableRecognitionRecord,
    build_receivable_recognition,
)
from backend.commercialization.receivable_writeoff import (
    CommercialReceivableWriteOffRecord,
    build_receivable_writeoff,
)


PERIOD_START = "2026-03-01T00:00:00+00:00"
PERIOD_END = "2026-04-01T00:00:00+00:00"
RECOGNIZED_AT = "2026-04-03T10:00:00+00:00"
ASSESSED_AT = "2026-04-04T11:00:00+00:00"
IDENTITY_AT = "2026-04-05T12:00:00+00:00"
ISSUED_AT = "2026-04-06T13:00:00+00:00"
RECEIVABLE_AT = "2026-04-08T15:00:00+00:00"
WRITTEN_OFF_AT = "2026-04-17T11:00:00+00:00"
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
    amount: Decimal = Decimal("100.00"),
) -> CommercialInvoiceIssuedRecord:
    obligation = CommercialBillableObligation(
        policy_id="POLICY-001",
        terms_id="TERMS-001",
        currency="CAD",
        period_start=PERIOD_START,
        period_end=PERIOD_END,
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
) -> CommercialReceivableRecognitionRecord:
    issued = _issued(invoice_id=invoice_id, amount=amount)
    return build_receivable_recognition(
        issued,
        receivable_id=receivable_id,
        recognized_at=RECEIVABLE_AT,
        evidence_refs=("receivable:OPS-1",),
        corrections=(),
    )


def _writeoff(
    receivable: CommercialReceivableRecognitionRecord | None = None,
    *,
    writeoff_id: str = "WO-A",
    writeoff_amount: Decimal = Decimal("20.00"),
    written_off_at: str = WRITTEN_OFF_AT,
    reason_reference: str = "reason:WRITEOFF-1",
    evidence_refs: tuple[str, ...] = ("writeoff:OPS-1",),
) -> CommercialReceivableWriteOffRecord:
    return build_receivable_writeoff(
        receivable or _receivable(),
        writeoff_id=writeoff_id,
        writeoff_amount=writeoff_amount,
        written_off_at=written_off_at,
        reason_reference=reason_reference,
        evidence_refs=evidence_refs,
    )


def _assert_all_safety_false(
    record: CommercialReceivableWriteOffRecord,
) -> None:
    assert record.receivable_mutation_allowed is False
    assert record.bad_debt_posting_allowed is False
    assert record.ledger_posting_allowed is False
    assert record.writeoff_accounting_posting_allowed is False
    assert record.payment_execution_allowed is False
    assert record.collection_initiation_allowed is False
    assert record.refund_allowed is False
    assert record.client_funds_deduction_allowed is False
    assert record.automatic_debit_allowed is False
    assert record.money_movement_allowed is False
    assert record.broker_withdrawal_allowed is False
    assert record.execution_authority is False


def test_valid_writeoff():
    receivable = _receivable()
    record = _writeoff(receivable)

    assert record.writeoff_id == "WO-A"
    assert record.receivable_id == "REC-A"
    assert record.invoice_id == "INV-A"
    assert record.currency == "CAD"
    assert record.writeoff_amount == Decimal("20.00")
    assert record.written_off_at == WRITTEN_OFF_AT
    assert record.reason_reference == "reason:WRITEOFF-1"
    assert record.evidence_refs == ("writeoff:OPS-1",)
    _assert_all_safety_false(record)


def test_writeoff_id_preserved_exactly():
    record = _writeoff(writeoff_id="WO-OPAQUE-9")
    assert record.writeoff_id == "WO-OPAQUE-9"


def test_receivable_id_copied_exactly():
    receivable = _receivable(receivable_id="REC-A")
    record = _writeoff(receivable)
    assert record.receivable_id == receivable.receivable_id
    assert record.receivable_id == "REC-A"


def test_invoice_id_copied_exactly():
    receivable = _receivable(invoice_id="INV-A")
    record = _writeoff(receivable)
    assert record.invoice_id == receivable.invoice_id
    assert record.invoice_id == "INV-A"


def test_currency_copied_exactly():
    receivable = _receivable()
    record = _writeoff(receivable)
    assert record.currency == receivable.currency
    assert record.currency == "CAD"


def test_exact_decimal_amount():
    record = _writeoff(writeoff_amount=Decimal("3.50"))
    assert record.writeoff_amount == Decimal("3.50")
    assert str(record.writeoff_amount) == "3.50"


def test_zero_amount_supported():
    record = _writeoff(writeoff_amount=Decimal("0"))
    assert record.writeoff_amount == Decimal("0")


def test_negative_amount_rejected():
    with pytest.raises(ValueError, match="writeoff_amount"):
        _writeoff(writeoff_amount=Decimal("-1"))


def test_float_amount_rejected():
    with pytest.raises(TypeError, match="writeoff_amount"):
        build_receivable_writeoff(
            _receivable(),
            writeoff_id="WO-A",
            writeoff_amount=20.0,  # type: ignore[arg-type]
            written_off_at=WRITTEN_OFF_AT,
            reason_reference="reason:WRITEOFF-1",
            evidence_refs=("writeoff:OPS-1",),
        )


def test_naive_written_off_at_rejected():
    with pytest.raises(ValueError, match="written_off_at"):
        _writeoff(written_off_at="2026-04-17T11:00:00")


def test_non_utc_written_off_at_rejected():
    with pytest.raises(ValueError, match="UTC"):
        _writeoff(written_off_at="2026-04-17T11:00:00-04:00")


def test_blank_writeoff_id_rejected():
    with pytest.raises(ValueError, match="writeoff_id"):
        _writeoff(writeoff_id=" ")


def test_blank_reason_reference_rejected():
    with pytest.raises(ValueError, match="reason_reference"):
        _writeoff(reason_reference=" ")


def test_evidence_required():
    with pytest.raises(ValueError, match="evidence_refs"):
        _writeoff(evidence_refs=())


def test_blank_evidence_rejected():
    with pytest.raises(ValueError, match="evidence"):
        _writeoff(evidence_refs=("writeoff:OPS-1", " "))


def test_object_immutable():
    record = _writeoff()
    with pytest.raises(FrozenInstanceError):
        record.writeoff_amount = Decimal("1")  # type: ignore[misc]


def test_no_due_date_gate():
    names = {
        f.name for f in fields(CommercialReceivableWriteOffRecord)
    }
    forbidden = {
        "due_date",
        "is_due",
        "is_overdue",
        "due_record_id",
    }
    assert names.isdisjoint(forbidden)
    record = _writeoff()
    assert not hasattr(record, "requires_due_date")


def test_no_bad_debt_status():
    names = {
        f.name for f in fields(CommercialReceivableWriteOffRecord)
    }
    forbidden = {
        "bad_debt_status",
        "impairment_status",
        "status",
        "writeoff_status",
    }
    assert names.isdisjoint(forbidden)


def test_no_journal_fields():
    names = {
        f.name for f in fields(CommercialReceivableWriteOffRecord)
    }
    forbidden = {
        "journal_id",
        "bad_debt_account",
        "allowance_account",
        "ar_account",
        "posting_status",
    }
    assert names.isdisjoint(forbidden)


def test_no_refund_fields():
    names = {
        f.name for f in fields(CommercialReceivableWriteOffRecord)
    }
    forbidden = {
        "refund_amount",
        "refund_status",
        "refund_id",
    }
    assert names.isdisjoint(forbidden)


def test_no_balance_fields():
    names = {
        f.name for f in fields(CommercialReceivableWriteOffRecord)
    }
    forbidden = {
        "outstanding_amount",
        "balance_due",
        "remaining_amount",
        "open_amount",
        "residual_amount",
    }
    assert names.isdisjoint(forbidden)


def test_all_safety_properties_false():
    _assert_all_safety_false(_writeoff())


def test_multiple_writeoffs_architecturally_supported():
    receivable = _receivable()
    writeoff_a = _writeoff(
        receivable,
        writeoff_id="WO-A",
        writeoff_amount=Decimal("10.00"),
    )
    writeoff_b = _writeoff(
        receivable,
        writeoff_id="WO-B",
        writeoff_amount=Decimal("5.00"),
    )
    assert writeoff_a.receivable_id == writeoff_b.receivable_id
    assert writeoff_a.writeoff_id != writeoff_b.writeoff_id
