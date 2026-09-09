from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Sequence, Tuple

from backend.commercialization.receivable_recognition import (
    CommercialReceivableRecognitionRecord,
)


class ReceivableWriteOffError(ValueError):
    """Base COM-002S receivable write-off contract error."""


class ReceivableWriteOffIneligibleError(ReceivableWriteOffError):
    """Raised when a receivable write-off record cannot proceed."""


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
class CommercialReceivableWriteOffRecord:
    """
    Immutable documentary recognition that an amount of one commercial
    receivable is no longer expected to be collected.

    Presence means write-off documentation only. It does not mutate
    the recognition row, post bad-debt GL, stop collection, refund,
    or move money.
    """

    writeoff_id: str
    receivable_id: str
    invoice_id: str
    currency: str
    writeoff_amount: Decimal
    written_off_at: str
    reason_reference: str
    evidence_refs: Tuple[str, ...]

    def __post_init__(self) -> None:
        _require_canonical_id("writeoff_id", self.writeoff_id)
        _require_canonical_id("receivable_id", self.receivable_id)
        _require_canonical_id("invoice_id", self.invoice_id)
        _require_canonical_id(
            "reason_reference",
            self.reason_reference,
        )
        _require_canonical_currency(self.currency)
        _parse_canonical_utc_timestamp(
            "written_off_at",
            self.written_off_at,
        )

        amount = _require_finite_decimal(
            "writeoff_amount",
            self.writeoff_amount,
        )
        if amount < Decimal("0"):
            raise ValueError(
                "writeoff_amount cannot be negative"
            )

        _require_evidence_refs(self.evidence_refs)

    @property
    def receivable_mutation_allowed(self) -> bool:
        return False

    @property
    def bad_debt_posting_allowed(self) -> bool:
        return False

    @property
    def ledger_posting_allowed(self) -> bool:
        return False

    @property
    def writeoff_accounting_posting_allowed(self) -> bool:
        return False

    @property
    def payment_execution_allowed(self) -> bool:
        return False

    @property
    def collection_initiation_allowed(self) -> bool:
        return False

    @property
    def refund_allowed(self) -> bool:
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


def build_receivable_writeoff(
    receivable: CommercialReceivableRecognitionRecord,
    *,
    writeoff_id: str,
    writeoff_amount: Decimal,
    written_off_at: str,
    reason_reference: str,
    evidence_refs: Tuple[str, ...],
) -> CommercialReceivableWriteOffRecord:
    """
    Fail-closed COM-002S documentary receivable write-off builder.

    Copies receivable_id, invoice_id, and currency from recognition.
    Does not inspect due dates or reversals, enforce aggregate caps,
    or post bad-debt GL.
    """

    if not isinstance(
        receivable,
        CommercialReceivableRecognitionRecord,
    ):
        raise TypeError(
            "receivable must be CommercialReceivableRecognitionRecord"
        )

    _require_canonical_id("writeoff_id", writeoff_id)
    _require_canonical_id("reason_reference", reason_reference)
    _parse_canonical_utc_timestamp("written_off_at", written_off_at)
    amount = _require_finite_decimal(
        "writeoff_amount",
        writeoff_amount,
    )
    if amount < Decimal("0"):
        raise ValueError("writeoff_amount cannot be negative")
    _require_evidence_refs(evidence_refs)

    return CommercialReceivableWriteOffRecord(
        writeoff_id=writeoff_id,
        receivable_id=receivable.receivable_id,
        invoice_id=receivable.invoice_id,
        currency=receivable.currency,
        writeoff_amount=writeoff_amount,
        written_off_at=written_off_at,
        reason_reference=reason_reference,
        evidence_refs=evidence_refs,
    )
