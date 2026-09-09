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
from backend.commercialization.receivable_credit import (
    CommercialReceivableCreditRecord,
    build_receivable_credit,
)
from backend.commercialization.receivable_recognition import (
    CommercialReceivableRecognitionRecord,
    build_receivable_recognition,
)


PERIOD_START = "2026-03-01T00:00:00+00:00"
PERIOD_END = "2026-04-01T00:00:00+00:00"
RECOGNIZED_AT = "2026-04-03T10:00:00+00:00"
ASSESSED_AT = "2026-04-04T11:00:00+00:00"
IDENTITY_AT = "2026-04-05T12:00:00+00:00"
ISSUED_AT = "2026-04-06T13:00:00+00:00"
RECEIVABLE_AT = "2026-04-08T15:00:00+00:00"
CREDITED_AT = "2026-04-16T10:00:00+00:00"
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


def _credit(
    receivable: CommercialReceivableRecognitionRecord | None = None,
    *,
    credit_id: str = "CR-A",
    credit_amount: Decimal = Decimal("15.00"),
    credited_at: str = CREDITED_AT,
    reason_reference: str = "reason:CREDIT-1",
    evidence_refs: tuple[str, ...] = ("credit:OPS-1",),
) -> CommercialReceivableCreditRecord:
    return build_receivable_credit(
        receivable or _receivable(),
        credit_id=credit_id,
        credit_amount=credit_amount,
        credited_at=credited_at,
        reason_reference=reason_reference,
        evidence_refs=evidence_refs,
    )


def _assert_all_safety_false(
    record: CommercialReceivableCreditRecord,
) -> None:
    assert record.receivable_mutation_allowed is False
    assert record.credit_note_creation_allowed is False
    assert record.refund_allowed is False
    assert record.ledger_posting_allowed is False
    assert record.revenue_adjustment_posting_allowed is False
    assert record.tax_recalculation_allowed is False
    assert record.payment_execution_allowed is False
    assert record.collection_initiation_allowed is False
    assert record.client_funds_deduction_allowed is False
    assert record.automatic_debit_allowed is False
    assert record.money_movement_allowed is False
    assert record.broker_withdrawal_allowed is False
    assert record.execution_authority is False


def test_valid_credit():
    receivable = _receivable()
    record = _credit(receivable)

    assert record.credit_id == "CR-A"
    assert record.receivable_id == "REC-A"
    assert record.invoice_id == "INV-A"
    assert record.currency == "CAD"
    assert record.credit_amount == Decimal("15.00")
    assert record.credited_at == CREDITED_AT
    assert record.reason_reference == "reason:CREDIT-1"
    assert record.evidence_refs == ("credit:OPS-1",)
    _assert_all_safety_false(record)


def test_credit_id_preserved_exactly():
    record = _credit(credit_id="CR-OPAQUE-9")
    assert record.credit_id == "CR-OPAQUE-9"


def test_receivable_id_copied_exactly():
    receivable = _receivable(receivable_id="REC-A")
    record = _credit(receivable)
    assert record.receivable_id == receivable.receivable_id
    assert record.receivable_id == "REC-A"


def test_invoice_id_copied_exactly():
    receivable = _receivable(invoice_id="INV-A")
    record = _credit(receivable)
    assert record.invoice_id == receivable.invoice_id
    assert record.invoice_id == "INV-A"


def test_currency_copied_exactly():
    receivable = _receivable()
    record = _credit(receivable)
    assert record.currency == receivable.currency
    assert record.currency == "CAD"


def test_exact_decimal_amount():
    record = _credit(credit_amount=Decimal("3.50"))
    assert record.credit_amount == Decimal("3.50")
    assert str(record.credit_amount) == "3.50"


def test_zero_amount_supported():
    record = _credit(credit_amount=Decimal("0"))
    assert record.credit_amount == Decimal("0")


def test_negative_amount_rejected():
    with pytest.raises(ValueError, match="credit_amount"):
        _credit(credit_amount=Decimal("-1"))


def test_float_amount_rejected():
    with pytest.raises(TypeError, match="credit_amount"):
        build_receivable_credit(
            _receivable(),
            credit_id="CR-A",
            credit_amount=15.0,  # type: ignore[arg-type]
            credited_at=CREDITED_AT,
            reason_reference="reason:CREDIT-1",
            evidence_refs=("credit:OPS-1",),
        )


def test_naive_credited_at_rejected():
    with pytest.raises(ValueError, match="credited_at"):
        _credit(credited_at="2026-04-16T10:00:00")


def test_non_utc_credited_at_rejected():
    with pytest.raises(ValueError, match="UTC"):
        _credit(credited_at="2026-04-16T10:00:00-04:00")


def test_blank_credit_id_rejected():
    with pytest.raises(ValueError, match="credit_id"):
        _credit(credit_id=" ")


def test_blank_reason_reference_rejected():
    with pytest.raises(ValueError, match="reason_reference"):
        _credit(reason_reference=" ")


def test_evidence_required():
    with pytest.raises(ValueError, match="evidence_refs"):
        _credit(evidence_refs=())


def test_blank_evidence_rejected():
    with pytest.raises(ValueError, match="evidence"):
        _credit(evidence_refs=("credit:OPS-1", " "))


def test_object_immutable():
    record = _credit()
    with pytest.raises(FrozenInstanceError):
        record.credit_amount = Decimal("1")  # type: ignore[misc]


def test_no_correction_id():
    names = {f.name for f in fields(CommercialReceivableCreditRecord)}
    assert "correction_id" not in names


def test_no_credit_note_id():
    names = {f.name for f in fields(CommercialReceivableCreditRecord)}
    forbidden = {
        "credit_note_id",
        "credit_note_number",
        "credit_document_status",
        "issued_at",
    }
    assert names.isdisjoint(forbidden)


def test_no_refund_fields():
    names = {f.name for f in fields(CommercialReceivableCreditRecord)}
    forbidden = {
        "refund_amount",
        "refund_status",
        "refund_id",
        "refund_authority",
    }
    assert names.isdisjoint(forbidden)


def test_no_gl_fields():
    names = {f.name for f in fields(CommercialReceivableCreditRecord)}
    forbidden = {
        "journal_id",
        "ar_account",
        "revenue_account",
        "posting_status",
        "tax_amount",
        "tax_code",
    }
    assert names.isdisjoint(forbidden)


def test_no_balance_fields():
    names = {f.name for f in fields(CommercialReceivableCreditRecord)}
    forbidden = {
        "outstanding_amount",
        "balance_due",
        "remaining_amount",
        "open_amount",
        "residual_amount",
    }
    assert names.isdisjoint(forbidden)


def test_all_safety_properties_false():
    _assert_all_safety_false(_credit())


def test_multiple_credits_architecturally_supported():
    receivable = _receivable()
    credit_a = _credit(
        receivable,
        credit_id="CR-A",
        credit_amount=Decimal("10.00"),
    )
    credit_b = _credit(
        receivable,
        credit_id="CR-B",
        credit_amount=Decimal("5.00"),
    )
    assert credit_a.receivable_id == credit_b.receivable_id
    assert credit_a.credit_id != credit_b.credit_id
