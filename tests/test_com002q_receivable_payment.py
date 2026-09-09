from dataclasses import FrozenInstanceError, fields
from decimal import Decimal

import pytest

from backend.commercialization.receivable_payment import (
    CommercialReceivablePaymentRecord,
    build_receivable_payment,
)


OBSERVED_AT = "2026-04-12T18:00:00+00:00"


def _payment(
    *,
    payment_id: str = "PAY-1",
    currency: str = "CAD",
    payment_amount: Decimal = Decimal("100.00"),
    observed_at: str = OBSERVED_AT,
    external_reference: str = "EXT-REF-001",
    evidence_refs: tuple[str, ...] = ("payment:OPS-1",),
) -> CommercialReceivablePaymentRecord:
    return build_receivable_payment(
        payment_id=payment_id,
        currency=currency,
        payment_amount=payment_amount,
        observed_at=observed_at,
        external_reference=external_reference,
        evidence_refs=evidence_refs,
    )


def _assert_all_safety_false(
    record: CommercialReceivablePaymentRecord,
) -> None:
    assert record.payment_execution_allowed is False
    assert record.collection_initiation_allowed is False
    assert record.client_funds_deduction_allowed is False
    assert record.automatic_debit_allowed is False
    assert record.bank_transfer_allowed is False
    assert record.ledger_posting_allowed is False
    assert record.cash_posting_allowed is False
    assert record.money_movement_allowed is False
    assert record.broker_withdrawal_allowed is False
    assert record.execution_authority is False


def test_valid_payment():
    record = _payment()

    assert record.payment_id == "PAY-1"
    assert record.currency == "CAD"
    assert record.payment_amount == Decimal("100.00")
    assert record.observed_at == OBSERVED_AT
    assert record.external_reference == "EXT-REF-001"
    assert record.evidence_refs == ("payment:OPS-1",)
    _assert_all_safety_false(record)


def test_payment_id_preserved_exactly():
    record = _payment(payment_id="PAY-OPAQUE-9")
    assert record.payment_id == "PAY-OPAQUE-9"


def test_uppercase_currency_accepted():
    record = _payment(currency="USD")
    assert record.currency == "USD"


def test_lowercase_currency_rejected():
    with pytest.raises(ValueError, match="currency"):
        _payment(currency="cad")


def test_decimal_amount_exact():
    record = _payment(payment_amount=Decimal("3.50"))
    assert record.payment_amount == Decimal("3.50")
    assert str(record.payment_amount) == "3.50"


def test_zero_amount_supported():
    record = _payment(payment_amount=Decimal("0"))
    assert record.payment_amount == Decimal("0")


def test_negative_amount_rejected():
    with pytest.raises(ValueError, match="payment_amount"):
        _payment(payment_amount=Decimal("-1"))


def test_float_amount_rejected():
    with pytest.raises(TypeError, match="payment_amount"):
        build_receivable_payment(
            payment_id="PAY-1",
            currency="CAD",
            payment_amount=100.0,  # type: ignore[arg-type]
            observed_at=OBSERVED_AT,
            external_reference="EXT-REF-001",
            evidence_refs=("payment:OPS-1",),
        )


def test_naive_observed_at_rejected():
    with pytest.raises(ValueError, match="observed_at"):
        _payment(observed_at="2026-04-12T18:00:00")


def test_non_utc_observed_at_rejected():
    with pytest.raises(ValueError, match="UTC"):
        _payment(observed_at="2026-04-12T18:00:00-04:00")


def test_blank_external_reference_rejected():
    with pytest.raises(ValueError, match="external_reference"):
        _payment(external_reference=" ")


def test_external_reference_canonical_stripping():
    record = _payment(external_reference="EXT-REF-001")
    assert record.external_reference == "EXT-REF-001"
    assert (
        record.external_reference
        == record.external_reference.strip()
    )

    with pytest.raises(ValueError, match="external_reference"):
        _payment(external_reference=" EXT-REF-001")


def test_missing_evidence_rejected():
    with pytest.raises(ValueError, match="evidence_refs"):
        _payment(evidence_refs=())


def test_blank_evidence_ref_rejected():
    with pytest.raises(ValueError, match="evidence"):
        _payment(evidence_refs=("payment:OPS-1", " "))


def test_object_immutable():
    record = _payment()
    with pytest.raises(FrozenInstanceError):
        record.payment_amount = Decimal("1")  # type: ignore[misc]


def test_no_receivable_id_field():
    names = {f.name for f in fields(CommercialReceivablePaymentRecord)}
    assert "receivable_id" not in names


def test_no_invoice_id_field():
    names = {f.name for f in fields(CommercialReceivablePaymentRecord)}
    assert "invoice_id" not in names
    assert "billing_profile_id" not in names


def test_no_payment_status():
    names = {f.name for f in fields(CommercialReceivablePaymentRecord)}
    forbidden = {
        "status",
        "payment_status",
        "settlement_status",
        "PENDING",
        "SETTLED",
        "CLEARED",
        "FAILED",
        "PAID",
        "PARTIALLY_PAID",
        "APPLIED",
        "UNAPPLIED",
        "payment_method",
        "bank_account",
        "transfer_id",
    }
    assert names.isdisjoint(forbidden)


def test_no_gl_fields():
    names = {f.name for f in fields(CommercialReceivablePaymentRecord)}
    forbidden = {
        "journal_id",
        "cash_account",
        "ar_account",
        "revenue_account",
        "posting_status",
        "cash_posted",
    }
    assert names.isdisjoint(forbidden)


def test_all_safety_properties_false():
    _assert_all_safety_false(_payment())
