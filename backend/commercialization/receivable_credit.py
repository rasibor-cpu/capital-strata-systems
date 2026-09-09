from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Sequence, Tuple

from backend.commercialization.receivable_recognition import (
    CommercialReceivableRecognitionRecord,
)


class ReceivableCreditError(ValueError):
    """Base COM-002S receivable credit contract error."""


class ReceivableCreditIneligibleError(ReceivableCreditError):
    """Raised when a receivable credit record cannot proceed."""


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
    Localized COM-002S datetime rule.

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
class CommercialReceivableCreditRecord:
    """
    Immutable documentary commercial reduction of one recognized
    receivable amount.

    Presence means credit adjustment only. It does not mutate the
    recognition row, issue a credit-note document, refund cash, post
    GL/tax, collect, or move money.
    """

    credit_id: str
    receivable_id: str
    invoice_id: str
    currency: str
    credit_amount: Decimal
    credited_at: str
    reason_reference: str
    evidence_refs: Tuple[str, ...]

    def __post_init__(self) -> None:
        _require_canonical_id("credit_id", self.credit_id)
        _require_canonical_id("receivable_id", self.receivable_id)
        _require_canonical_id("invoice_id", self.invoice_id)
        _require_canonical_id(
            "reason_reference",
            self.reason_reference,
        )
        _require_canonical_currency(self.currency)
        _parse_canonical_utc_timestamp(
            "credited_at",
            self.credited_at,
        )

        amount = _require_finite_decimal(
            "credit_amount",
            self.credit_amount,
        )
        if amount < Decimal("0"):
            raise ValueError(
                "credit_amount cannot be negative"
            )

        _require_evidence_refs(self.evidence_refs)

    @property
    def receivable_mutation_allowed(self) -> bool:
        return False

    @property
    def credit_note_creation_allowed(self) -> bool:
        return False

    @property
    def refund_allowed(self) -> bool:
        return False

    @property
    def ledger_posting_allowed(self) -> bool:
        return False

    @property
    def revenue_adjustment_posting_allowed(self) -> bool:
        return False

    @property
    def tax_recalculation_allowed(self) -> bool:
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
    def money_movement_allowed(self) -> bool:
        return False

    @property
    def broker_withdrawal_allowed(self) -> bool:
        return False

    @property
    def execution_authority(self) -> bool:
        return False


def build_receivable_credit(
    receivable: CommercialReceivableRecognitionRecord,
    *,
    credit_id: str,
    credit_amount: Decimal,
    credited_at: str,
    reason_reference: str,
    evidence_refs: Tuple[str, ...],
) -> CommercialReceivableCreditRecord:
    """
    Fail-closed COM-002S documentary receivable credit builder.

    Copies receivable_id, invoice_id, and currency from recognition.
    Does not inspect reversals, enforce aggregate caps, issue credit
    notes, refund, or post GL.
    """

    if not isinstance(
        receivable,
        CommercialReceivableRecognitionRecord,
    ):
        raise TypeError(
            "receivable must be CommercialReceivableRecognitionRecord"
        )

    _require_canonical_id("credit_id", credit_id)
    _require_canonical_id("reason_reference", reason_reference)
    _parse_canonical_utc_timestamp("credited_at", credited_at)
    amount = _require_finite_decimal(
        "credit_amount",
        credit_amount,
    )
    if amount < Decimal("0"):
        raise ValueError("credit_amount cannot be negative")
    _require_evidence_refs(evidence_refs)

    return CommercialReceivableCreditRecord(
        credit_id=credit_id,
        receivable_id=receivable.receivable_id,
        invoice_id=receivable.invoice_id,
        currency=receivable.currency,
        credit_amount=credit_amount,
        credited_at=credited_at,
        reason_reference=reason_reference,
        evidence_refs=evidence_refs,
    )
