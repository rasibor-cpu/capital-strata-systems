from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Sequence, Tuple

from backend.commercialization.receivable_payment import (
    CommercialReceivablePaymentRecord,
)
from backend.commercialization.receivable_recognition import (
    CommercialReceivableRecognitionRecord,
)


class ReceivablePaymentAllocationError(ValueError):
    """Base COM-002Q receivable payment-allocation contract error."""


class ReceivablePaymentAllocationIneligibleError(
    ReceivablePaymentAllocationError,
):
    """Raised when a payment allocation record cannot proceed."""


def _require_canonical_id(name: str, value: str) -> None:
    if not value or value != value.strip():
        raise ValueError(
            f"{name} is required and must be canonical"
        )


def _require_canonical_currency(currency: str) -> None:
    if (
        not currency
        or currency != currency.strip()
        or currency != currency.upper()
    ):
        raise ValueError(
            "currency must be canonical uppercase text"
        )


def _require_finite_decimal(name: str, value: object) -> Decimal:
    if not isinstance(value, Decimal):
        raise TypeError(f"{name} must be Decimal")

    if not value.is_finite():
        raise ValueError(f"{name} must be finite")

    return value


def _require_evidence_refs(evidence_refs: Sequence[str]) -> None:
    if not evidence_refs:
        raise ValueError("evidence_refs must be non-empty")

    for ref in evidence_refs:
        if not isinstance(ref, str) or not ref or ref != ref.strip():
            raise ValueError(
                "evidence refs must be nonblank canonical strings"
            )


def _parse_canonical_utc_timestamp(name: str, value: str) -> datetime:
    """
    Localized COM-002Q datetime rule.

    Accepts timezone-aware ISO-8601 timestamps whose offset is UTC
    (+00:00 or Z). Naive datetimes and non-UTC offsets are rejected.
    """

    if not value or value != value.strip():
        raise ValueError(
            f"{name} is required and must be canonical"
        )

    text = value.strip()
    try:
        parsed = datetime.fromisoformat(
            text.replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise ValueError(
            f"{name} must be timezone-aware UTC ISO-8601"
        ) from exc

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(
            f"{name} must be timezone-aware UTC ISO-8601"
        )

    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError(
            f"{name} must use UTC offset only"
        )

    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class CommercialReceivablePaymentAllocationRecord:
    """
    Immutable documentary record that an amount from an evidenced
    commercial payment has been allocated to one recognized receivable.

    Presence means documentary allocation only. It does not execute
    payment, mutate receivable/payment balances, post cash/GL, credit,
    write off, refund, or authorize collection.
    """

    allocation_id: str
    payment_id: str
    receivable_id: str
    invoice_id: str
    currency: str
    allocated_amount: Decimal
    allocated_at: str
    evidence_refs: Tuple[str, ...]

    def __post_init__(self) -> None:
        _require_canonical_id("allocation_id", self.allocation_id)
        _require_canonical_id("payment_id", self.payment_id)
        _require_canonical_id("receivable_id", self.receivable_id)
        _require_canonical_id("invoice_id", self.invoice_id)
        _require_canonical_currency(self.currency)
        _parse_canonical_utc_timestamp(
            "allocated_at",
            self.allocated_at,
        )

        amount = _require_finite_decimal(
            "allocated_amount",
            self.allocated_amount,
        )
        if amount < Decimal("0"):
            raise ValueError(
                "allocated_amount cannot be negative"
            )

        _require_evidence_refs(self.evidence_refs)

    @property
    def payment_execution_allowed(self) -> bool:
        return False

    @property
    def receivable_mutation_allowed(self) -> bool:
        return False

    @property
    def outstanding_balance_mutation_allowed(self) -> bool:
        return False

    @property
    def aggregate_allocation_validation_allowed(self) -> bool:
        return False

    @property
    def cash_application_authority(self) -> bool:
        return False

    @property
    def collection_initiation_allowed(self) -> bool:
        return False

    @property
    def client_funds_deduction_allowed(self) -> bool:
        return False

    @property
    def automatic_debit_allowed(self) -> bool:
        return False

    @property
    def ledger_posting_allowed(self) -> bool:
        return False

    @property
    def cash_posting_allowed(self) -> bool:
        return False

    @property
    def credit_note_creation_allowed(self) -> bool:
        return False

    @property
    def writeoff_allowed(self) -> bool:
        return False

    @property
    def refund_allowed(self) -> bool:
        return False

    @property
    def money_movement_allowed(self) -> bool:
        return False

    @property
    def broker_withdrawal_allowed(self) -> bool:
        return False

    @property
    def execution_authority(self) -> bool:
        return False


def build_receivable_payment_allocation(
    payment: CommercialReceivablePaymentRecord,
    receivable: CommercialReceivableRecognitionRecord,
    *,
    allocation_id: str,
    allocated_amount: Decimal,
    allocated_at: str,
    evidence_refs: Tuple[str, ...],
) -> CommercialReceivablePaymentAllocationRecord:
    """
    Fail-closed COM-002Q documentary payment-allocation builder.

    Copies payment_id from the payment and receivable_id/invoice_id from
    the recognition. Requires matching currencies. Caps a single
    allocation by payment_amount only. Does not aggregate prior
    allocations, derive open balance, or invent overpayment policy.
    """

    if not isinstance(payment, CommercialReceivablePaymentRecord):
        raise TypeError(
            "payment must be CommercialReceivablePaymentRecord"
        )

    if not isinstance(
        receivable,
        CommercialReceivableRecognitionRecord,
    ):
        raise TypeError(
            "receivable must be CommercialReceivableRecognitionRecord"
        )

    _require_canonical_id("allocation_id", allocation_id)
    _parse_canonical_utc_timestamp("allocated_at", allocated_at)
    amount = _require_finite_decimal(
        "allocated_amount",
        allocated_amount,
    )
    if amount < Decimal("0"):
        raise ValueError("allocated_amount cannot be negative")
    _require_evidence_refs(evidence_refs)

    if payment.currency != receivable.currency:
        raise ReceivablePaymentAllocationIneligibleError(
            "payment currency must match receivable currency"
        )

    if amount > payment.payment_amount:
        raise ReceivablePaymentAllocationIneligibleError(
            "allocated_amount cannot exceed payment_amount"
        )

    return CommercialReceivablePaymentAllocationRecord(
        allocation_id=allocation_id,
        payment_id=payment.payment_id,
        receivable_id=receivable.receivable_id,
        invoice_id=receivable.invoice_id,
        currency=payment.currency,
        allocated_amount=allocated_amount,
        allocated_at=allocated_at,
        evidence_refs=evidence_refs,
    )
