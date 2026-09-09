from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Sequence, Tuple

from backend.commercialization.invoice_issued import (
    CommercialInvoiceIssuedRecord,
)


class InvoiceCorrectionError(ValueError):
    """Base COM-002M invoice-correction contract error."""


class InvoiceCorrectionType(str, Enum):
    """
    Documentary correction event types for an immutable issued invoice.

    Stage 1 deliberately excludes CREDIT, CANCEL, REFUND, WRITE_OFF,
    and any accounting/payment correction vocabulary.
    """

    VOID = "VOID"
    SUPERSEDE = "SUPERSEDE"


def _require_canonical_id(name: str, value: str) -> None:
    if not value or value != value.strip():
        raise ValueError(
            f"{name} is required and must be canonical"
        )


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
    Localized COM-002M datetime rule.

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
class CommercialInvoiceCorrectionRecord:
    """
    Immutable append-only documentary correction event for one issued
    commercial invoice.

    Presence of this record expresses a VOID or SUPERSEDE event. It does
    not mutate the issued invoice, create credit notes, adjust
    receivables, reverse ledger/revenue, refund, pay, or execute.
    """

    correction_id: str
    invoice_id: str
    correction_type: InvoiceCorrectionType
    corrected_at: str
    reason_reference: str
    evidence_refs: Tuple[str, ...]
    replacement_invoice_id: Optional[str] = None

    def __post_init__(self) -> None:
        _require_canonical_id("correction_id", self.correction_id)
        _require_canonical_id("invoice_id", self.invoice_id)
        _require_canonical_id(
            "reason_reference",
            self.reason_reference,
        )

        if not isinstance(self.correction_type, InvoiceCorrectionType):
            raise TypeError(
                "correction_type must be InvoiceCorrectionType"
            )

        _parse_canonical_utc_timestamp(
            "corrected_at",
            self.corrected_at,
        )
        _require_evidence_refs(self.evidence_refs)

        if self.correction_type is InvoiceCorrectionType.VOID:
            if self.replacement_invoice_id is not None:
                raise InvoiceCorrectionError(
                    "VOID requires replacement_invoice_id=None"
                )
        elif self.correction_type is InvoiceCorrectionType.SUPERSEDE:
            if self.replacement_invoice_id is None:
                raise InvoiceCorrectionError(
                    "SUPERSEDE requires replacement_invoice_id"
                )
            _require_canonical_id(
                "replacement_invoice_id",
                self.replacement_invoice_id,
            )
            if self.replacement_invoice_id == self.invoice_id:
                raise InvoiceCorrectionError(
                    "replacement_invoice_id must differ from invoice_id"
                )

    @property
    def issued_invoice_mutation_allowed(self) -> bool:
        return False

    @property
    def credit_note_creation_allowed(self) -> bool:
        return False

    @property
    def receivable_adjustment_allowed(self) -> bool:
        return False

    @property
    def ledger_reversal_allowed(self) -> bool:
        return False

    @property
    def revenue_reversal_allowed(self) -> bool:
        return False

    @property
    def refund_allowed(self) -> bool:
        return False

    @property
    def payment_initiation_allowed(self) -> bool:
        return False

    @property
    def money_movement_allowed(self) -> bool:
        return False

    @property
    def client_funds_deduction_allowed(self) -> bool:
        return False

    @property
    def automatic_debit_allowed(self) -> bool:
        return False

    @property
    def broker_withdrawal_allowed(self) -> bool:
        return False

    @property
    def execution_authority(self) -> bool:
        return False

    @property
    def replacement_invoice_creation_allowed(self) -> bool:
        return False


def build_invoice_correction(
    issued_record: CommercialInvoiceIssuedRecord,
    *,
    correction_id: str,
    correction_type: InvoiceCorrectionType,
    corrected_at: str,
    reason_reference: str,
    evidence_refs: Tuple[str, ...],
    replacement_invoice: Optional[
        CommercialInvoiceIssuedRecord
    ] = None,
) -> CommercialInvoiceCorrectionRecord:
    """
    Fail-closed COM-002M documentary invoice-correction builder.

    Records VOID or SUPERSEDE against an existing issued invoice without
    mutating that invoice or creating a replacement invoice.
    """

    if not isinstance(issued_record, CommercialInvoiceIssuedRecord):
        raise TypeError(
            "issued_record must be CommercialInvoiceIssuedRecord"
        )

    if not isinstance(correction_type, InvoiceCorrectionType):
        raise TypeError(
            "correction_type must be InvoiceCorrectionType"
        )

    _require_canonical_id("correction_id", correction_id)
    _require_canonical_id("reason_reference", reason_reference)
    _parse_canonical_utc_timestamp("corrected_at", corrected_at)
    _require_evidence_refs(evidence_refs)

    replacement_invoice_id: Optional[str] = None

    if correction_type is InvoiceCorrectionType.VOID:
        if replacement_invoice is not None:
            raise InvoiceCorrectionError(
                "VOID requires replacement_invoice=None"
            )
    elif correction_type is InvoiceCorrectionType.SUPERSEDE:
        if replacement_invoice is None:
            raise InvoiceCorrectionError(
                "SUPERSEDE requires replacement_invoice"
            )
        if not isinstance(
            replacement_invoice,
            CommercialInvoiceIssuedRecord,
        ):
            raise TypeError(
                "replacement_invoice must be "
                "CommercialInvoiceIssuedRecord"
            )
        if (
            replacement_invoice.invoice_id
            == issued_record.invoice_id
        ):
            raise InvoiceCorrectionError(
                "replacement_invoice_id must differ from invoice_id"
            )
        replacement_invoice_id = replacement_invoice.invoice_id

    return CommercialInvoiceCorrectionRecord(
        correction_id=correction_id,
        invoice_id=issued_record.invoice_id,
        correction_type=correction_type,
        corrected_at=corrected_at,
        reason_reference=reason_reference,
        evidence_refs=evidence_refs,
        replacement_invoice_id=replacement_invoice_id,
    )
