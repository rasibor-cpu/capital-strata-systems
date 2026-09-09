from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Sequence, Tuple

from backend.commercialization.receivable_recognition import (
    CommercialReceivableRecognitionRecord,
)
from backend.commercialization.receivable_reversal import (
    CommercialReceivableReversalRecord,
)


class ReceivableDueError(ValueError):
    """Base COM-002P receivable due-date contract error."""


class ReceivableDueIneligibleError(ReceivableDueError):
    """Raised when a receivable due-date record cannot proceed."""


_CALENDAR_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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


def _require_calendar_date(name: str, value: str) -> str:
    """
    Accept exactly a valid ISO-8601 civil calendar date YYYY-MM-DD.

    Rejects timestamps, noncanonical formats, and impossible dates.
    Does not attach timezone, shift business days, or apply calendars.
    """

    if not value or value != value.strip():
        raise ValueError(
            f"{name} is required and must be canonical YYYY-MM-DD"
        )

    if not _CALENDAR_DATE_RE.fullmatch(value):
        raise ValueError(
            f"{name} must be a valid YYYY-MM-DD calendar date"
        )

    try:
        year, month, day = (int(part) for part in value.split("-"))
        date(year, month, day)
    except ValueError as exc:
        raise ValueError(
            f"{name} must be a valid YYYY-MM-DD calendar date"
        ) from exc

    return value


def _parse_canonical_utc_timestamp(name: str, value: str) -> datetime:
    """
    Localized COM-002P datetime rule.

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
class CommercialReceivableDueRecord:
    """
    Immutable documentary record that one recognized commercial
    receivable has an externally determined civil calendar due date.

    Presence means due-date determination only. It does not assert
    currently-due/overdue status, outstanding balance, payment,
    collection, ageing storage, GL posting, or money movement.
    """

    due_record_id: str
    receivable_id: str
    invoice_id: str
    due_date: str
    determined_at: str
    terms_reference: str
    evidence_refs: Tuple[str, ...]

    def __post_init__(self) -> None:
        _require_canonical_id("due_record_id", self.due_record_id)
        _require_canonical_id("receivable_id", self.receivable_id)
        _require_canonical_id("invoice_id", self.invoice_id)
        _require_canonical_id(
            "terms_reference",
            self.terms_reference,
        )
        _require_calendar_date("due_date", self.due_date)
        _parse_canonical_utc_timestamp(
            "determined_at",
            self.determined_at,
        )
        _require_evidence_refs(self.evidence_refs)

    @property
    def receivable_mutation_allowed(self) -> bool:
        return False

    @property
    def due_status_mutation_allowed(self) -> bool:
        return False

    @property
    def overdue_status_creation_allowed(self) -> bool:
        return False

    @property
    def ageing_state_storage_allowed(self) -> bool:
        return False

    @property
    def outstanding_balance_creation_allowed(self) -> bool:
        return False

    @property
    def outstanding_balance_mutation_allowed(self) -> bool:
        return False

    @property
    def payment_terms_calculation_allowed(self) -> bool:
        return False

    @property
    def payment_allocation_allowed(self) -> bool:
        return False

    @property
    def credit_note_creation_allowed(self) -> bool:
        return False

    @property
    def writeoff_allowed(self) -> bool:
        return False

    @property
    def ledger_posting_allowed(self) -> bool:
        return False

    @property
    def revenue_recognition_posting_allowed(self) -> bool:
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
    def collection_initiation_allowed(self) -> bool:
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


def build_receivable_due_record(
    receivable: CommercialReceivableRecognitionRecord,
    *,
    due_record_id: str,
    due_date: str,
    determined_at: str,
    terms_reference: str,
    evidence_refs: Tuple[str, ...],
    reversals: Tuple[CommercialReceivableReversalRecord, ...] = (),
) -> CommercialReceivableDueRecord:
    """
    Fail-closed COM-002P documentary receivable due-date builder.

    Copies receivable_id and invoice_id from recognition. Stores the
    caller-supplied civil calendar due date as an external fact. Rejects
    when the reversals snapshot is inconsistent or includes any full
    reversal for this receivable.
    """

    if not isinstance(
        receivable,
        CommercialReceivableRecognitionRecord,
    ):
        raise TypeError(
            "receivable must be CommercialReceivableRecognitionRecord"
        )

    _require_canonical_id("due_record_id", due_record_id)
    _require_canonical_id("terms_reference", terms_reference)
    _require_calendar_date("due_date", due_date)
    _parse_canonical_utc_timestamp("determined_at", determined_at)
    _require_evidence_refs(evidence_refs)

    for reversal in reversals:
        if not isinstance(
            reversal,
            CommercialReceivableReversalRecord,
        ):
            raise TypeError(
                "reversals must contain "
                "CommercialReceivableReversalRecord values"
            )
        if reversal.receivable_id != receivable.receivable_id:
            raise ReceivableDueIneligibleError(
                "reversals snapshot is inconsistent with receivable"
            )
        raise ReceivableDueIneligibleError(
            "full receivable reversal blocks due-date determination"
        )

    return CommercialReceivableDueRecord(
        due_record_id=due_record_id,
        receivable_id=receivable.receivable_id,
        invoice_id=receivable.invoice_id,
        due_date=due_date,
        determined_at=determined_at,
        terms_reference=terms_reference,
        evidence_refs=evidence_refs,
    )
