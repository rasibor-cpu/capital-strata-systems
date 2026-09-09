from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Sequence, Tuple

from backend.commercialization.invoice_identity import (
    CommercialInvoiceIdentityAllocation,
)


class InvoiceIssuedError(ValueError):
    """Base COM-002L invoice-issuance record contract error."""


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
    Localized COM-002L datetime rule.

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
class CommercialInvoiceIssuedRecord:
    """
    Immutable documentary issuance record for one commercial invoice
    identity allocation.

    Presence of this record means the allocation has been issued as a
    commercial document. It does not create receivables, due balances,
    tax amounts, ledger postings, payments, collections, corrections,
    credit notes, or execution.
    """

    invoice_id: str
    policy_id: str
    terms_id: str
    billing_profile_id: str
    currency: str
    period_start: str
    period_end: str
    invoice_amount: Decimal
    invoice_number: Optional[str]
    issued_at: str
    evidence_refs: Tuple[str, ...]

    def __post_init__(self) -> None:
        _require_canonical_id("invoice_id", self.invoice_id)
        _require_canonical_id("policy_id", self.policy_id)
        _require_canonical_id("terms_id", self.terms_id)
        _require_canonical_id(
            "billing_profile_id",
            self.billing_profile_id,
        )
        _require_canonical_currency(self.currency)

        period_start = _parse_canonical_utc_timestamp(
            "period_start",
            self.period_start,
        )
        period_end = _parse_canonical_utc_timestamp(
            "period_end",
            self.period_end,
        )
        _parse_canonical_utc_timestamp(
            "issued_at",
            self.issued_at,
        )

        if period_end <= period_start:
            raise ValueError(
                "period_end must be after period_start"
            )

        amount = _require_finite_decimal(
            "invoice_amount",
            self.invoice_amount,
        )

        if amount < Decimal("0"):
            raise ValueError(
                "invoice_amount cannot be negative"
            )

        if self.invoice_number is not None:
            _require_canonical_id(
                "invoice_number",
                self.invoice_number,
            )

        _require_evidence_refs(self.evidence_refs)

    @property
    def receivable_recognition_allowed(self) -> bool:
        return False

    @property
    def ledger_posting_allowed(self) -> bool:
        return False

    @property
    def revenue_recognition_allowed(self) -> bool:
        return False

    @property
    def tax_calculation_allowed(self) -> bool:
        return False

    @property
    def due_balance_creation_allowed(self) -> bool:
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
    def invoice_settlement_allowed(self) -> bool:
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
    def correction_allowed(self) -> bool:
        return False

    @property
    def credit_note_creation_allowed(self) -> bool:
        return False


def build_invoice_issued_record(
    allocation: CommercialInvoiceIdentityAllocation,
    *,
    issued_at: str,
    evidence_refs: Tuple[str, ...],
) -> CommercialInvoiceIssuedRecord:
    """
    Fail-closed COM-002L documentary invoice-issuance builder.

    Copies identity and economics from an existing invoice identity
    allocation. Does not generate numbers, recalculate amounts, create
    receivables, or authorize payment.
    """

    if not isinstance(allocation, CommercialInvoiceIdentityAllocation):
        raise TypeError(
            "allocation must be CommercialInvoiceIdentityAllocation"
        )

    _parse_canonical_utc_timestamp("issued_at", issued_at)
    _require_evidence_refs(evidence_refs)

    return CommercialInvoiceIssuedRecord(
        invoice_id=allocation.invoice_id,
        policy_id=allocation.policy_id,
        terms_id=allocation.terms_id,
        billing_profile_id=allocation.billing_profile_id,
        currency=allocation.currency,
        period_start=allocation.period_start,
        period_end=allocation.period_end,
        invoice_amount=allocation.invoice_amount,
        invoice_number=allocation.invoice_number,
        issued_at=issued_at,
        evidence_refs=evidence_refs,
    )
