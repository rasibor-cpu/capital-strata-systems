from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Sequence, Tuple

from backend.commercialization.billable_obligation import (
    BillableObligationStatus,
    CommercialBillableObligation,
)
from backend.commercialization.billing_profile import (
    CommercialBillingProfile,
)


class InvoiceCandidateError(ValueError):
    """Base COM-002J invoice-candidate contract error."""


class InvoiceCandidateIneligibleError(InvoiceCandidateError):
    """Raised when an invoice candidate cannot be established."""


class InvoiceCandidateStatus(str, Enum):
    """
    Explicit pre-invoice readiness for one billable commercial period
    paired with a commercial billing profile.

    Deliberately excludes invoice/receivable/money-state vocabulary
    such as ISSUED, INVOICED, DUE, PAID, COLLECTED, VOID, or CREDITED.
    """

    NOT_READY = "NOT_READY"
    READY = "READY"
    BLOCKED = "BLOCKED"
    EXPIRED = "EXPIRED"


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
    Localized COM-002J datetime rule.

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
class CommercialInvoiceCandidate:
    """
    Immutable pre-invoice candidate for one billable commercial period
    paired with a commercial billing profile.

    Keyed one-to-one with the billable period by:
    (policy_id, period_start, period_end)

    READY means only that a BILLABLE obligation and an invoice-ready
    billing profile have been explicitly paired as a future invoice
    candidate. It does not issue an invoice, assign invoice numbers,
    create receivables, due balances, tax amounts, ledger postings,
    payments, collections, or execution.
    """

    policy_id: str
    terms_id: str
    billing_profile_id: str
    currency: str
    period_start: str
    period_end: str
    candidate_amount: Decimal
    assessed_at: str
    status: InvoiceCandidateStatus
    evidence_refs: Tuple[str, ...]

    def __post_init__(self) -> None:
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
            "assessed_at",
            self.assessed_at,
        )

        if period_end <= period_start:
            raise ValueError(
                "period_end must be after period_start"
            )

        amount = _require_finite_decimal(
            "candidate_amount",
            self.candidate_amount,
        )

        if amount < Decimal("0"):
            raise ValueError(
                "candidate_amount cannot be negative"
            )

        if not isinstance(self.status, InvoiceCandidateStatus):
            raise TypeError(
                "status must be InvoiceCandidateStatus"
            )

        _require_evidence_refs(self.evidence_refs)

    @property
    def invoice_creation_allowed(self) -> bool:
        return False

    @property
    def invoice_number_assignment_allowed(self) -> bool:
        return False

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


def _require_profile_effectivity_overlap(
    obligation: CommercialBillableObligation,
    billing_profile: CommercialBillingProfile,
) -> None:
    period_start = _parse_canonical_utc_timestamp(
        "period_start",
        obligation.period_start,
    )
    period_end = _parse_canonical_utc_timestamp(
        "period_end",
        obligation.period_end,
    )
    profile_from = _parse_canonical_utc_timestamp(
        "effective_from",
        billing_profile.effective_from,
    )

    if profile_from > period_end:
        raise InvoiceCandidateError(
            "billing profile must overlap obligation period"
        )

    if billing_profile.effective_to is not None:
        profile_to = _parse_canonical_utc_timestamp(
            "effective_to",
            billing_profile.effective_to,
        )
        if profile_to <= period_start:
            raise InvoiceCandidateError(
                "billing profile must overlap obligation period"
            )


def build_invoice_candidate(
    obligation: CommercialBillableObligation,
    billing_profile: CommercialBillingProfile,
    status: InvoiceCandidateStatus,
    assessed_at: str,
    evidence_refs: Tuple[str, ...],
) -> CommercialInvoiceCandidate:
    """
    Fail-closed COM-002J invoice-candidate builder.

    Pairs a billable obligation with a billing profile. Does not
    recalculate economics or billing-profile readiness gates.
    READY requires BILLABLE obligation and invoice_candidate_ready
    profile.
    """

    if not isinstance(obligation, CommercialBillableObligation):
        raise TypeError(
            "obligation must be CommercialBillableObligation"
        )

    if not isinstance(billing_profile, CommercialBillingProfile):
        raise TypeError(
            "billing_profile must be CommercialBillingProfile"
        )

    if not isinstance(status, InvoiceCandidateStatus):
        raise TypeError(
            "status must be InvoiceCandidateStatus"
        )

    _parse_canonical_utc_timestamp("assessed_at", assessed_at)
    _require_evidence_refs(evidence_refs)

    if obligation.terms_id != billing_profile.terms_id:
        raise InvoiceCandidateError(
            "obligation and billing profile terms_id must match"
        )

    _require_profile_effectivity_overlap(
        obligation,
        billing_profile,
    )

    if status == InvoiceCandidateStatus.READY:
        if obligation.status != BillableObligationStatus.BILLABLE:
            raise InvoiceCandidateIneligibleError(
                "READY requires BILLABLE obligation"
            )

        if not billing_profile.invoice_candidate_ready:
            raise InvoiceCandidateIneligibleError(
                "READY requires invoice-ready billing profile"
            )

    return CommercialInvoiceCandidate(
        policy_id=obligation.policy_id,
        terms_id=obligation.terms_id,
        billing_profile_id=billing_profile.billing_profile_id,
        currency=obligation.currency,
        period_start=obligation.period_start,
        period_end=obligation.period_end,
        candidate_amount=obligation.billable_amount,
        assessed_at=assessed_at,
        status=status,
        evidence_refs=evidence_refs,
    )
