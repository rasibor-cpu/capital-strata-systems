from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Sequence, Tuple

from backend.commercialization.invoice_correction import (
    CommercialInvoiceCorrectionRecord,
    InvoiceCorrectionType,
)
from backend.commercialization.invoice_issued import (
    CommercialInvoiceIssuedRecord,
)


class ReceivableRecognitionError(ValueError):
    """Base COM-002N receivable-recognition contract error."""


class ReceivableRecognitionIneligibleError(ReceivableRecognitionError):
    """Raised when receivable recognition cannot proceed."""


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
    Localized COM-002N datetime rule.

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
class CommercialReceivableRecognitionRecord:
    """
    Immutable documentary recognition that one issued commercial invoice
    has been recognized as a commercial receivable.

    Presence of this record means recognition only. It does not post to
    the ledger, create due balances, track outstanding amounts, authorize
    payment/collection, calculate tax, or move money.
    """

    receivable_id: str
    invoice_id: str
    billing_profile_id: str
    currency: str
    receivable_amount: Decimal
    recognized_at: str
    evidence_refs: Tuple[str, ...]

    def __post_init__(self) -> None:
        _require_canonical_id("receivable_id", self.receivable_id)
        _require_canonical_id("invoice_id", self.invoice_id)
        _require_canonical_id(
            "billing_profile_id",
            self.billing_profile_id,
        )
        _require_canonical_currency(self.currency)
        _parse_canonical_utc_timestamp(
            "recognized_at",
            self.recognized_at,
        )

        amount = _require_finite_decimal(
            "receivable_amount",
            self.receivable_amount,
        )

        if amount < Decimal("0"):
            raise ValueError(
                "receivable_amount cannot be negative"
            )

        _require_evidence_refs(self.evidence_refs)

    @property
    def ledger_posting_allowed(self) -> bool:
        return False

    @property
    def revenue_recognition_posting_allowed(self) -> bool:
        return False

    @property
    def due_balance_creation_allowed(self) -> bool:
        return False

    @property
    def outstanding_balance_tracking_allowed(self) -> bool:
        return False

    @property
    def payment_allocation_allowed(self) -> bool:
        return False

    @property
    def credit_note_creation_allowed(self) -> bool:
        return False

    @property
    def receivable_adjustment_allowed(self) -> bool:
        return False

    @property
    def writeoff_allowed(self) -> bool:
        return False

    @property
    def real_fee_collection_allowed(self) -> bool:
        return False

    @property
    def client_funds_deduction_allowed(self) -> bool:
        return False

    @property
    def automatic_debit_allowed(self) -> bool:
        return False

    @property
    def payment_initiation_allowed(self) -> bool:
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
    def post_recognition_correction_handling_allowed(self) -> bool:
        return False


def build_receivable_recognition(
    issued_record: CommercialInvoiceIssuedRecord,
    *,
    receivable_id: str,
    recognized_at: str,
    evidence_refs: Tuple[str, ...],
    corrections: Tuple[CommercialInvoiceCorrectionRecord, ...] = (),
) -> CommercialReceivableRecognitionRecord:
    """
    Fail-closed COM-002N documentary receivable-recognition builder.

    Copies economics and billing context from an issued invoice. Rejects
    recognition when the supplied corrections snapshot includes VOID or
    SUPERSEDE for that invoice, or any correction for a different
    invoice_id. Does not post, due, collect, or auto-recognize
    replacements.
    """

    if not isinstance(issued_record, CommercialInvoiceIssuedRecord):
        raise TypeError(
            "issued_record must be CommercialInvoiceIssuedRecord"
        )

    _require_canonical_id("receivable_id", receivable_id)
    _parse_canonical_utc_timestamp("recognized_at", recognized_at)
    _require_evidence_refs(evidence_refs)

    for correction in corrections:
        if not isinstance(
            correction,
            CommercialInvoiceCorrectionRecord,
        ):
            raise TypeError(
                "corrections must contain "
                "CommercialInvoiceCorrectionRecord values"
            )
        if correction.invoice_id != issued_record.invoice_id:
            raise ReceivableRecognitionIneligibleError(
                "corrections snapshot is inconsistent with issued invoice"
            )
        if correction.correction_type in (
            InvoiceCorrectionType.VOID,
            InvoiceCorrectionType.SUPERSEDE,
        ):
            raise ReceivableRecognitionIneligibleError(
                "VOID or SUPERSEDE correction blocks receivable recognition"
            )

    return CommercialReceivableRecognitionRecord(
        receivable_id=receivable_id,
        invoice_id=issued_record.invoice_id,
        billing_profile_id=issued_record.billing_profile_id,
        currency=issued_record.currency,
        receivable_amount=issued_record.invoice_amount,
        recognized_at=recognized_at,
        evidence_refs=evidence_refs,
    )
