from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Sequence, Tuple


class BillingProfileError(ValueError):
    """Base COM-002I billing-profile contract error."""


class BillingPartyType(str, Enum):
    """Commercial bill-to party classification."""

    INDIVIDUAL = "INDIVIDUAL"
    ORGANIZATION = "ORGANIZATION"


class TaxTreatmentStatus(str, Enum):
    """
    Tax readiness/status only.

    Does not calculate tax, specify rates, or assert jurisdiction.
    """

    UNDETERMINED = "UNDETERMINED"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    EXEMPT = "EXEMPT"
    REQUIRES_DETERMINATION = "REQUIRES_DETERMINATION"


class PaymentTermsStatus(str, Enum):
    """
    Payment-terms readiness/status only.

    Does not define net days, due dates, or grace periods.
    """

    UNDETERMINED = "UNDETERMINED"
    NOT_REQUIRED = "NOT_REQUIRED"
    REQUIRES_DEFINITION = "REQUIRES_DEFINITION"
    DEFINED_EXTERNALLY = "DEFINED_EXTERNALLY"


def _require_canonical_text(name: str, value: str) -> None:
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
    Localized COM-002I datetime rule.

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
class CommercialBillingProfile:
    """
    Immutable commercial billing identity/context bound to one
    PerformanceCompensationTerms record.

    Establishes commercial bill-to / seller context before invoice
    readiness. It does not create invoices, receivables, due balances,
    tax amounts, ledger postings, payments, collections, or execution.
    """

    billing_profile_id: str
    terms_id: str
    party_type: BillingPartyType
    bill_to_name: str
    bill_to_reference: str
    seller_reference: str
    tax_treatment_status: TaxTreatmentStatus
    payment_terms_status: PaymentTermsStatus
    effective_from: str
    evidence_refs: Tuple[str, ...]
    effective_to: Optional[str] = None

    def __post_init__(self) -> None:
        _require_canonical_text(
            "billing_profile_id",
            self.billing_profile_id,
        )
        _require_canonical_text("terms_id", self.terms_id)
        _require_canonical_text("bill_to_name", self.bill_to_name)
        _require_canonical_text(
            "bill_to_reference",
            self.bill_to_reference,
        )
        _require_canonical_text(
            "seller_reference",
            self.seller_reference,
        )

        if not isinstance(self.party_type, BillingPartyType):
            raise TypeError("party_type must be BillingPartyType")

        if not isinstance(
            self.tax_treatment_status,
            TaxTreatmentStatus,
        ):
            raise TypeError(
                "tax_treatment_status must be TaxTreatmentStatus"
            )

        if not isinstance(
            self.payment_terms_status,
            PaymentTermsStatus,
        ):
            raise TypeError(
                "payment_terms_status must be PaymentTermsStatus"
            )

        effective_from = _parse_canonical_utc_timestamp(
            "effective_from",
            self.effective_from,
        )

        if self.effective_to is not None:
            effective_to = _parse_canonical_utc_timestamp(
                "effective_to",
                self.effective_to,
            )
            if effective_to <= effective_from:
                raise ValueError(
                    "effective_to must be after effective_from"
                )

        _require_evidence_refs(self.evidence_refs)

    @property
    def invoice_identity_ready(self) -> bool:
        return bool(
            self.bill_to_name.strip()
            and self.bill_to_reference.strip()
            and self.seller_reference.strip()
        )

    @property
    def tax_ready(self) -> bool:
        return self.tax_treatment_status in (
            TaxTreatmentStatus.OUT_OF_SCOPE,
            TaxTreatmentStatus.EXEMPT,
        )

    @property
    def payment_terms_ready(self) -> bool:
        return self.payment_terms_status in (
            PaymentTermsStatus.NOT_REQUIRED,
            PaymentTermsStatus.DEFINED_EXTERNALLY,
        )

    @property
    def invoice_candidate_ready(self) -> bool:
        return (
            self.invoice_identity_ready
            and self.tax_ready
            and self.payment_terms_ready
        )

    @property
    def invoice_creation_allowed(self) -> bool:
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


def build_commercial_billing_profile(
    *,
    billing_profile_id: str,
    terms_id: str,
    party_type: BillingPartyType,
    bill_to_name: str,
    bill_to_reference: str,
    seller_reference: str,
    tax_treatment_status: TaxTreatmentStatus,
    payment_terms_status: PaymentTermsStatus,
    effective_from: str,
    evidence_refs: Tuple[str, ...],
    effective_to: Optional[str] = None,
) -> CommercialBillingProfile:
    """
    Fail-closed COM-002I billing-profile builder.

    Validates commercial billing identity/context only. Does not look
    up trading customers, broker accounts, GL accounts, or legal
    acceptances.
    """

    return CommercialBillingProfile(
        billing_profile_id=billing_profile_id,
        terms_id=terms_id,
        party_type=party_type,
        bill_to_name=bill_to_name,
        bill_to_reference=bill_to_reference,
        seller_reference=seller_reference,
        tax_treatment_status=tax_treatment_status,
        payment_terms_status=payment_terms_status,
        effective_from=effective_from,
        evidence_refs=evidence_refs,
        effective_to=effective_to,
    )
