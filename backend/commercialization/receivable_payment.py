from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Sequence, Tuple


class ReceivablePaymentError(ValueError):
    """Base COM-002Q commercial payment contract error."""


class ReceivablePaymentIneligibleError(ReceivablePaymentError):
    """Raised when a commercial payment record cannot proceed."""


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
class CommercialReceivablePaymentRecord:
    """
    Immutable documentary record that an external commercial payment
    has been observed/confirmed.

    Payment identity is independent of any receivable. Presence means
    observation only. It does not initiate payment, collect, transfer,
    post cash/GL, mutate balances, refund, or move money.
    """

    payment_id: str
    currency: str
    payment_amount: Decimal
    observed_at: str
    external_reference: str
    evidence_refs: Tuple[str, ...]

    def __post_init__(self) -> None:
        _require_canonical_id("payment_id", self.payment_id)
        _require_canonical_currency(self.currency)
        _require_canonical_id(
            "external_reference",
            self.external_reference,
        )
        _parse_canonical_utc_timestamp(
            "observed_at",
            self.observed_at,
        )

        amount = _require_finite_decimal(
            "payment_amount",
            self.payment_amount,
        )
        if amount < Decimal("0"):
            raise ValueError(
                "payment_amount cannot be negative"
            )

        _require_evidence_refs(self.evidence_refs)

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
    def bank_transfer_allowed(self) -> bool:
        return False

    @property
    def ledger_posting_allowed(self) -> bool:
        return False

    @property
    def cash_posting_allowed(self) -> bool:
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


def build_receivable_payment(
    *,
    payment_id: str,
    currency: str,
    payment_amount: Decimal,
    observed_at: str,
    external_reference: str,
    evidence_refs: Tuple[str, ...],
) -> CommercialReceivablePaymentRecord:
    """
    Fail-closed COM-002Q documentary commercial payment builder.

    Stores an externally observed payment with independent payment_id.
    Does not link receivables, initiate payment, or post cash/GL.
    """

    _require_canonical_id("payment_id", payment_id)
    _require_canonical_currency(currency)
    _require_canonical_id("external_reference", external_reference)
    _parse_canonical_utc_timestamp("observed_at", observed_at)
    amount = _require_finite_decimal(
        "payment_amount",
        payment_amount,
    )
    if amount < Decimal("0"):
        raise ValueError("payment_amount cannot be negative")
    _require_evidence_refs(evidence_refs)

    return CommercialReceivablePaymentRecord(
        payment_id=payment_id,
        currency=currency,
        payment_amount=payment_amount,
        observed_at=observed_at,
        external_reference=external_reference,
        evidence_refs=evidence_refs,
    )
