from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import Tuple

from backend.commercialization.receivable_credit import CommercialReceivableCreditRecord
from backend.commercialization.receivable_writeoff import CommercialReceivableWriteOffRecord
from backend.commercialization.receivable_payment_allocation import CommercialReceivablePaymentAllocationRecord
from backend.commercialization.receivable_recognition import (
    CommercialReceivableRecognitionRecord,
    _parse_canonical_utc_timestamp,
    _require_finite_decimal,
    _require_canonical_id,
    _require_canonical_currency,
)
from backend.commercialization.receivable_reversal import CommercialReceivableReversalRecord


class ReceivableEconomicResidualError(ValueError):
    """Base COM-002T economic residual projection error."""


class ReceivableEconomicResidualIneligibleError(ReceivableEconomicResidualError):
    """Raised when an economic residual snapshot is inconsistent."""


def _exact_sum(amounts: Tuple[Decimal, ...]) -> Decimal:
    """Allow every coefficient digit and carry without ambient-context rounding."""
    if not amounts:
        return Decimal("0")
    lowest = min(value.as_tuple().exponent for value in amounts)
    highest = max(value.adjusted() for value in amounts)
    with localcontext() as context:
        context.prec = max(1, highest - lowest + 1) + len(str(len(amounts)))
        return sum(amounts, Decimal("0"))


@dataclass(frozen=True, slots=True)
class CommercialReceivableEconomicResidualProjection:
    """Pure documentary residual; grants no execution or posting authority."""

    receivable_id: str
    invoice_id: str
    currency: str
    as_of: str
    recognized_amount: Decimal
    reversed_amount: Decimal
    allocated_amount: Decimal
    credited_amount: Decimal
    written_off_amount: Decimal
    economic_residual_amount: Decimal
    payment_events_included: bool = True
    credit_events_included: bool = True
    writeoff_events_included: bool = True
    is_complete_economic_residual: bool = True

    def __post_init__(self) -> None:
        _require_canonical_id("receivable_id", self.receivable_id)
        _require_canonical_id("invoice_id", self.invoice_id)
        _require_canonical_currency(self.currency)
        _parse_canonical_utc_timestamp("as_of", self.as_of)
        for name in (
            "recognized_amount", "reversed_amount", "allocated_amount",
            "credited_amount", "written_off_amount", "economic_residual_amount",
        ):
            if _require_finite_decimal(name, getattr(self, name)) < Decimal("0"):
                raise ValueError(f"{name} cannot be negative")
        for name in (
            "payment_events_included", "credit_events_included",
            "writeoff_events_included", "is_complete_economic_residual",
        ):
            if getattr(self, name) is not True:
                raise ValueError(f"{name} must be True")

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


def build_receivable_economic_residual_projection(
    recognition: CommercialReceivableRecognitionRecord,
    *,
    as_of: str,
    reversal: CommercialReceivableReversalRecord | None = None,
    allocations: Tuple[CommercialReceivablePaymentAllocationRecord, ...] = (),
    credits: Tuple[CommercialReceivableCreditRecord, ...] = (),
    writeoffs: Tuple[CommercialReceivableWriteOffRecord, ...] = (),
) -> CommercialReceivableEconomicResidualProjection:
    """Project a caller-supplied as-of snapshot without persistence or mutation.

    The caller supplies the correct as-of snapshot. Events are never filtered
    by timestamp. Full reversal preserves historical reduction aggregates,
    even when their combined amount exceeds recognition.
    """
    if not isinstance(recognition, CommercialReceivableRecognitionRecord):
        raise TypeError("recognition must be CommercialReceivableRecognitionRecord")
    _parse_canonical_utc_timestamp("as_of", as_of)
    totals = []
    for snapshot, record_type, id_name, amount_name in (
        (allocations, CommercialReceivablePaymentAllocationRecord, "allocation_id", "allocated_amount"),
        (credits, CommercialReceivableCreditRecord, "credit_id", "credit_amount"),
        (writeoffs, CommercialReceivableWriteOffRecord, "writeoff_id", "writeoff_amount"),
    ):
        seen: set[str] = set()
        amounts = []
        for event in snapshot:
            if not isinstance(event, record_type):
                raise TypeError(f"snapshot must contain {record_type.__name__} values")
            event_id = getattr(event, id_name)
            if event_id in seen:
                raise ReceivableEconomicResidualIneligibleError(f"duplicate {id_name} in snapshot")
            seen.add(event_id)
            for name in ("receivable_id", "invoice_id", "currency"):
                if getattr(event, name) != getattr(recognition, name):
                    raise ReceivableEconomicResidualIneligibleError(
                        f"{id_name} {name} inconsistent with recognition"
                    )
            amounts.append(getattr(event, amount_name))
        totals.append(_exact_sum(tuple(amounts)))

    recognized_amount = recognition.receivable_amount
    reversed_amount = Decimal("0")
    if reversal is not None:
        if not isinstance(reversal, CommercialReceivableReversalRecord):
            raise TypeError("reversal must be CommercialReceivableReversalRecord")
        for name in ("receivable_id", "invoice_id", "currency"):
            if getattr(reversal, name) != getattr(recognition, name):
                raise ReceivableEconomicResidualIneligibleError(
                    f"reversal {name} inconsistent with recognition"
                )
        if reversal.reversal_amount != recognized_amount:
            raise ReceivableEconomicResidualIneligibleError(
                "reversal_amount must equal receivable_amount"
            )
        reversed_amount = recognized_amount
        residual = Decimal("0")
    else:
        reductions = _exact_sum(tuple(totals))
        if reductions > recognized_amount:
            raise ReceivableEconomicResidualIneligibleError(
                "total reductions exceed recognized_amount"
            )
        residual = _exact_sum((recognized_amount, reductions.copy_negate()))

    return CommercialReceivableEconomicResidualProjection(
        receivable_id=recognition.receivable_id,
        invoice_id=recognition.invoice_id,
        currency=recognition.currency,
        as_of=as_of,
        recognized_amount=recognized_amount,
        reversed_amount=reversed_amount,
        allocated_amount=totals[0],
        credited_amount=totals[1],
        written_off_amount=totals[2],
        economic_residual_amount=residual,
    )
