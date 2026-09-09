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
    CommercialInvoiceCandidate,
    InvoiceCandidateStatus,
    build_invoice_candidate,
)
from backend.commercialization.invoice_identity import (
    CommercialInvoiceIdentityAllocation,
    build_invoice_identity_allocation,
)
from backend.commercialization.invoice_issued import (
    CommercialInvoiceIssuedRecord,
    build_invoice_issued_record,
)


PERIOD_START = "2026-03-01T00:00:00+00:00"
PERIOD_END = "2026-04-01T00:00:00+00:00"
RECOGNIZED_AT = "2026-04-03T10:00:00+00:00"
ASSESSED_AT = "2026-04-04T11:00:00+00:00"
ALLOCATED_AT = "2026-04-05T12:00:00+00:00"
ISSUED_AT = "2026-04-06T13:00:00+00:00"
PROFILE_FROM = "2026-01-01T00:00:00+00:00"
PROFILE_TO = "2026-12-31T00:00:00+00:00"


def _obligation(
    *,
    billable_amount: Decimal = Decimal("1"),
) -> CommercialBillableObligation:
    return CommercialBillableObligation(
        policy_id="POLICY-001",
        terms_id="TERMS-001",
        currency="CAD",
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        billable_amount=billable_amount,
        recognized_at=RECOGNIZED_AT,
        status=BillableObligationStatus.BILLABLE,
        evidence_refs=("billable:OPS-1",),
    )


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


def _candidate(
    *,
    candidate_amount: Decimal = Decimal("1"),
) -> CommercialInvoiceCandidate:
    return build_invoice_candidate(
        _obligation(billable_amount=candidate_amount),
        _profile(),
        InvoiceCandidateStatus.READY,
        ASSESSED_AT,
        ("candidate:OPS-1",),
    )


def _allocation(
    *,
    candidate_amount: Decimal = Decimal("1"),
    invoice_id: str = "INV-ID-001",
    invoice_number: str | None = None,
) -> CommercialInvoiceIdentityAllocation:
    return build_invoice_identity_allocation(
        _candidate(candidate_amount=candidate_amount),
        invoice_id=invoice_id,
        allocated_at=ALLOCATED_AT,
        evidence_refs=("identity:OPS-1",),
        invoice_number=invoice_number,
    )


def _issued(
    allocation: CommercialInvoiceIdentityAllocation | None = None,
    *,
    issued_at: str = ISSUED_AT,
    evidence_refs: tuple[str, ...] = ("issued:OPS-1",),
) -> CommercialInvoiceIssuedRecord:
    return build_invoice_issued_record(
        allocation if allocation is not None else _allocation(),
        issued_at=issued_at,
        evidence_refs=evidence_refs,
    )


def _assert_all_safety_false(
    record: CommercialInvoiceIssuedRecord,
) -> None:
    assert record.receivable_recognition_allowed is False
    assert record.ledger_posting_allowed is False
    assert record.revenue_recognition_allowed is False
    assert record.tax_calculation_allowed is False
    assert record.due_balance_creation_allowed is False
    assert record.real_fee_collection_allowed is False
    assert record.client_funds_deduction_allowed is False
    assert record.automatic_debit_allowed is False
    assert record.invoice_settlement_allowed is False
    assert record.payment_initiation_allowed is False
    assert record.money_movement_allowed is False
    assert record.broker_withdrawal_allowed is False
    assert record.execution_authority is False
    assert record.correction_allowed is False
    assert record.credit_note_creation_allowed is False


def test_valid_issued_record_with_invoice_number_none():
    allocation = _allocation(invoice_number=None)
    record = _issued(allocation)

    assert record.invoice_id == allocation.invoice_id
    assert record.policy_id == allocation.policy_id
    assert record.terms_id == allocation.terms_id
    assert record.billing_profile_id == allocation.billing_profile_id
    assert record.currency == allocation.currency
    assert record.period_start == allocation.period_start
    assert record.period_end == allocation.period_end
    assert record.invoice_amount == allocation.invoice_amount
    assert record.invoice_number is None
    assert record.issued_at == ISSUED_AT
    assert record.evidence_refs == ("issued:OPS-1",)
    _assert_all_safety_false(record)


def test_valid_issued_record_with_invoice_number_present():
    allocation = _allocation(invoice_number="INV-2026-0001")
    record = _issued(allocation)

    assert record.invoice_number == "INV-2026-0001"
    assert record.invoice_number == allocation.invoice_number
    _assert_all_safety_false(record)


def test_invoice_id_copied_exactly():
    allocation = _allocation(invoice_id="INV-ID-OPAQUE-9")
    record = _issued(allocation)
    assert record.invoice_id == "INV-ID-OPAQUE-9"
    assert record.invoice_id == allocation.invoice_id


def test_invoice_number_copied_exactly():
    allocation = _allocation(invoice_number="INV-2026-0001")
    record = _issued(allocation)
    assert record.invoice_number == "INV-2026-0001"


def test_invoice_amount_copied_exactly():
    allocation = _allocation(candidate_amount=Decimal("1.00"))
    record = _issued(allocation)
    assert record.invoice_amount == Decimal("1.00")
    assert record.invoice_amount == allocation.invoice_amount
    assert record.invoice_amount != Decimal("3")
    assert record.invoice_amount != Decimal("5")
    assert record.invoice_amount != Decimal("15")


def test_zero_amount_supported():
    allocation = _allocation(candidate_amount=Decimal("0"))
    record = _issued(allocation)
    assert record.invoice_amount == Decimal("0")


def test_decimal_representation_preserved():
    amount = Decimal("1.2500")
    allocation = _allocation(candidate_amount=amount)
    record = _issued(allocation)
    assert record.invoice_amount == amount
    assert format(record.invoice_amount, "f") == "1.2500"


def test_no_economic_recalculation():
    allocation = _allocation(candidate_amount=Decimal("1.00"))
    record = _issued(allocation)
    assert record.invoice_amount is allocation.invoice_amount
    assert record.invoice_amount == Decimal("1.00")


def test_blank_invoice_id_rejected_direct_construction():
    with pytest.raises(ValueError, match="invoice_id"):
        CommercialInvoiceIssuedRecord(
            invoice_id=" ",
            policy_id="POLICY-001",
            terms_id="TERMS-001",
            billing_profile_id="BP-001",
            currency="CAD",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            invoice_amount=Decimal("1"),
            invoice_number=None,
            issued_at=ISSUED_AT,
            evidence_refs=("issued:OPS-1",),
        )


def test_blank_policy_id_rejected():
    with pytest.raises(ValueError, match="policy_id"):
        CommercialInvoiceIssuedRecord(
            invoice_id="INV-ID-001",
            policy_id="",
            terms_id="TERMS-001",
            billing_profile_id="BP-001",
            currency="CAD",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            invoice_amount=Decimal("1"),
            invoice_number=None,
            issued_at=ISSUED_AT,
            evidence_refs=("issued:OPS-1",),
        )


def test_blank_terms_id_rejected():
    with pytest.raises(ValueError, match="terms_id"):
        CommercialInvoiceIssuedRecord(
            invoice_id="INV-ID-001",
            policy_id="POLICY-001",
            terms_id=" ",
            billing_profile_id="BP-001",
            currency="CAD",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            invoice_amount=Decimal("1"),
            invoice_number=None,
            issued_at=ISSUED_AT,
            evidence_refs=("issued:OPS-1",),
        )


def test_blank_billing_profile_id_rejected():
    with pytest.raises(ValueError, match="billing_profile_id"):
        CommercialInvoiceIssuedRecord(
            invoice_id="INV-ID-001",
            policy_id="POLICY-001",
            terms_id="TERMS-001",
            billing_profile_id="",
            currency="CAD",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            invoice_amount=Decimal("1"),
            invoice_number=None,
            issued_at=ISSUED_AT,
            evidence_refs=("issued:OPS-1",),
        )


def test_lowercase_currency_rejected():
    with pytest.raises(ValueError, match="currency"):
        CommercialInvoiceIssuedRecord(
            invoice_id="INV-ID-001",
            policy_id="POLICY-001",
            terms_id="TERMS-001",
            billing_profile_id="BP-001",
            currency="cad",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            invoice_amount=Decimal("1"),
            invoice_number=None,
            issued_at=ISSUED_AT,
            evidence_refs=("issued:OPS-1",),
        )


def test_naive_issued_at_rejected():
    with pytest.raises(ValueError, match="issued_at"):
        _issued(issued_at="2026-04-06T13:00:00")


def test_non_utc_issued_at_rejected():
    with pytest.raises(ValueError, match="UTC"):
        _issued(issued_at="2026-04-06T13:00:00-04:00")


def test_invalid_period_ordering_rejected():
    with pytest.raises(ValueError, match="period_end"):
        CommercialInvoiceIssuedRecord(
            invoice_id="INV-ID-001",
            policy_id="POLICY-001",
            terms_id="TERMS-001",
            billing_profile_id="BP-001",
            currency="CAD",
            period_start=PERIOD_END,
            period_end=PERIOD_START,
            invoice_amount=Decimal("1"),
            invoice_number=None,
            issued_at=ISSUED_AT,
            evidence_refs=("issued:OPS-1",),
        )


def test_missing_evidence_rejected():
    with pytest.raises(ValueError, match="evidence_refs"):
        _issued(evidence_refs=())


def test_blank_evidence_ref_rejected():
    with pytest.raises(ValueError, match="evidence"):
        _issued(evidence_refs=(" ",))


def test_object_immutable():
    record = _issued()
    with pytest.raises(FrozenInstanceError):
        record.invoice_id = "OTHER"  # type: ignore[misc]


def test_no_status_field_exists():
    names = {field.name for field in fields(CommercialInvoiceIssuedRecord)}
    assert "status" not in names
    assert "invoice_status" not in names


def test_no_due_date_field_exists():
    names = {field.name for field in fields(CommercialInvoiceIssuedRecord)}
    assert "due_date" not in names
    assert "net_days" not in names


def test_no_receivable_tax_posting_fields_exist():
    names = {field.name for field in fields(CommercialInvoiceIssuedRecord)}
    forbidden = {
        "receivable_id",
        "amount_due",
        "balance_due",
        "tax_rate",
        "tax_amount",
        "tax_jurisdiction",
        "journal_id",
        "ar_account",
        "issued_record_id",
        "document_id",
    }
    assert names.isdisjoint(forbidden)


def test_z_suffix_issued_at_accepted():
    record = _issued(issued_at="2026-04-06T13:00:00Z")
    assert record.issued_at == "2026-04-06T13:00:00Z"
