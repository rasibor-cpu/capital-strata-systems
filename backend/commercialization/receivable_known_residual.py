from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Tuple

from backend.commercialization.receivable_payment_allocation import (
    CommercialReceivablePaymentAllocationRecord,
)
from backend.commercialization.receivable_recognition import (
    CommercialReceivableRecognitionRecord,
)
from backend.commercialization.receivable_reversal import (
    CommercialReceivableReversalRecord,
)


class ReceivableKnownResidualError(ValueError):
    """Base COM-002R known residual projection error."""


class ReceivableKnownResidualIneligibleError(
    ReceivableKnownResidualError,
):
    """Raised when a known residual projection cannot proceed."""


def _parse_canonical_utc_timestamp(name: str, value: str) -> datetime:
    """
    Localized COM-002R datetime rule.

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
class CommercialReceivableKnownResidualProjection:
    """
    Immutable pure projection of known residual for one commercial
    receivable from currently modeled event types only.

    This is not a complete AR open/outstanding balance. Credit and
    write-off streams are unsupported. Presence of residual_amount
    means only recognition minus full reversal and payment allocations
    under the Stage 1 rules.
    """

    receivable_id: str
    invoice_id: str
    currency: str
    as_of: str
    recognized_amount: Decimal
    reversed_amount: Decimal
    allocated_amount: Decimal
    residual_amount: Decimal
    payment_events_included: bool
    credit_events_supported: bool
    writeoff_events_supported: bool
    is_complete_balance: bool

    def __post_init__(self) -> None:
        if self.payment_events_included is not True:
            raise ValueError(
                "payment_events_included must be True"
            )
        if self.credit_events_supported is not False:
            raise ValueError(
                "credit_events_supported must be False"
            )
        if self.writeoff_events_supported is not False:
            raise ValueError(
                "writeoff_events_supported must be False"
            )
        if self.is_complete_balance is not False:
            raise ValueError(
                "is_complete_balance must be False"
            )

        _parse_canonical_utc_timestamp("as_of", self.as_of)

        if self.residual_amount < Decimal("0"):
            raise ValueError(
                "residual_amount cannot be negative"
            )

    @property
    def mutable_balance_allowed(self) -> bool:
        return False

    @property
    def receivable_mutation_allowed(self) -> bool:
        return False

    @property
    def payment_execution_allowed(self) -> bool:
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

    @property
    def complete_balance_claim_allowed(self) -> bool:
        return False

    @property
    def overpayment_resolution_allowed(self) -> bool:
        return False


def build_receivable_known_residual_projection(
    recognition: CommercialReceivableRecognitionRecord,
    *,
    as_of: str,
    reversal: CommercialReceivableReversalRecord | None = None,
    allocations: Tuple[
        CommercialReceivablePaymentAllocationRecord,
        ...,
    ] = (),
) -> CommercialReceivableKnownResidualProjection:
    """
    Fail-closed COM-002R pure known residual projector.

    Derives residual from recognition, optional full reversal, and a
    caller-supplied allocation snapshot. Does not filter by as_of,
    read repositories, mutate state, or invent complete AR balance,
    credit, write-off, or overpayment semantics.
    """

    if not isinstance(
        recognition,
        CommercialReceivableRecognitionRecord,
    ):
        raise TypeError(
            "recognition must be CommercialReceivableRecognitionRecord"
        )

    _parse_canonical_utc_timestamp("as_of", as_of)

    recognized_amount = recognition.receivable_amount
    seen_allocation_ids: set[str] = set()
    allocated_amount = Decimal("0")

    for allocation in allocations:
        if not isinstance(
            allocation,
            CommercialReceivablePaymentAllocationRecord,
        ):
            raise TypeError(
                "allocations must contain "
                "CommercialReceivablePaymentAllocationRecord values"
            )

        if allocation.allocation_id in seen_allocation_ids:
            raise ReceivableKnownResidualIneligibleError(
                "duplicate allocation_id in snapshot"
            )
        seen_allocation_ids.add(allocation.allocation_id)

        if allocation.receivable_id != recognition.receivable_id:
            raise ReceivableKnownResidualIneligibleError(
                "allocation receivable_id inconsistent with recognition"
            )
        if allocation.invoice_id != recognition.invoice_id:
            raise ReceivableKnownResidualIneligibleError(
                "allocation invoice_id inconsistent with recognition"
            )
        if allocation.currency != recognition.currency:
            raise ReceivableKnownResidualIneligibleError(
                "allocation currency inconsistent with recognition"
            )

        allocated_amount += allocation.allocated_amount

    if reversal is None:
        reversed_amount = Decimal("0")
        if allocated_amount > recognized_amount:
            raise ReceivableKnownResidualIneligibleError(
                "aggregate allocated_amount exceeds recognized_amount"
            )
        residual_amount = recognized_amount - allocated_amount
    else:
        if not isinstance(
            reversal,
            CommercialReceivableReversalRecord,
        ):
            raise TypeError(
                "reversal must be CommercialReceivableReversalRecord"
            )

        if reversal.receivable_id != recognition.receivable_id:
            raise ReceivableKnownResidualIneligibleError(
                "reversal receivable_id inconsistent with recognition"
            )
        if reversal.invoice_id != recognition.invoice_id:
            raise ReceivableKnownResidualIneligibleError(
                "reversal invoice_id inconsistent with recognition"
            )
        if reversal.currency != recognition.currency:
            raise ReceivableKnownResidualIneligibleError(
                "reversal currency inconsistent with recognition"
            )
        if reversal.reversal_amount != recognition.receivable_amount:
            raise ReceivableKnownResidualIneligibleError(
                "reversal_amount must equal receivable_amount"
            )

        reversed_amount = recognition.receivable_amount
        residual_amount = Decimal("0")

    return CommercialReceivableKnownResidualProjection(
        receivable_id=recognition.receivable_id,
        invoice_id=recognition.invoice_id,
        currency=recognition.currency,
        as_of=as_of,
        recognized_amount=recognized_amount,
        reversed_amount=reversed_amount,
        allocated_amount=allocated_amount,
        residual_amount=residual_amount,
        payment_events_included=True,
        credit_events_supported=False,
        writeoff_events_supported=False,
        is_complete_balance=False,
    )
