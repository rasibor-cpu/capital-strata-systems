from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Tuple


class TrialContractError(ValueError):
    """Base error for commercial trial/contract controls."""


class TrialConversionStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    TRIAL_ACTIVE = "TRIAL_ACTIVE"
    ELIGIBLE_TO_CONVERT = "ELIGIBLE_TO_CONVERT"
    CANCELED = "CANCELED"
    BLOCKED = "BLOCKED"


def _utc(name: str, value: str) -> datetime:
    if not value or value != value.strip():
        raise ValueError(f"{name} is required and must be canonical")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError(f"{name} must use UTC")
    return parsed.astimezone(timezone.utc)


def _canonical(name: str, value: str) -> None:
    if not value or value != value.strip():
        raise ValueError(f"{name} is required and must be canonical")


@dataclass(frozen=True, slots=True)
class CommercialAgreementSnapshot:
    """Exact customer agreement/pricing snapshot shown before trial enrollment."""

    agreement_id: str
    agreement_version: str
    jurisdiction_code: str
    pricing_plan_id: str
    pricing_summary: str
    trial_duration_days: int
    automatic_conversion_disclosure: str
    effective_from: str
    evidence_refs: Tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "agreement_id",
            "agreement_version",
            "jurisdiction_code",
            "pricing_plan_id",
            "pricing_summary",
            "automatic_conversion_disclosure",
        ):
            _canonical(name, getattr(self, name))
        _utc("effective_from", self.effective_from)
        if self.trial_duration_days <= 0:
            raise ValueError("trial_duration_days must be positive")
        if not isinstance(self.evidence_refs, tuple) or not self.evidence_refs:
            raise ValueError("agreement requires immutable evidence refs")


@dataclass(frozen=True, slots=True)
class TrialEnrollment:
    """Immutable evidence of affirmative acceptance and trial start."""

    customer_id: str
    account_reference: str
    agreement_id: str
    agreement_version: str
    pricing_plan_id: str
    accepted_at: str
    trial_start_at: str
    trial_expires_at: str
    displayed_pricing_summary: str
    displayed_conversion_disclosure: str
    acceptance_audit_reference: str
    evidence_refs: Tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "customer_id",
            "account_reference",
            "agreement_id",
            "agreement_version",
            "pricing_plan_id",
            "displayed_pricing_summary",
            "displayed_conversion_disclosure",
            "acceptance_audit_reference",
        ):
            _canonical(name, getattr(self, name))

        accepted = _utc("accepted_at", self.accepted_at)
        start = _utc("trial_start_at", self.trial_start_at)
        expiry = _utc("trial_expires_at", self.trial_expires_at)
        if start < accepted:
            raise ValueError("trial_start_at cannot precede acceptance")
        if expiry <= start:
            raise ValueError("trial_expires_at must be after trial_start_at")
        if not isinstance(self.evidence_refs, tuple) or not self.evidence_refs:
            raise ValueError("trial enrollment requires immutable evidence refs")


@dataclass(frozen=True, slots=True)
class TrialCancellation:
    """Immutable customer cancellation event."""

    customer_id: str
    account_reference: str
    canceled_at: str
    cancellation_audit_reference: str
    evidence_refs: Tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "customer_id",
            "account_reference",
            "cancellation_audit_reference",
        ):
            _canonical(name, getattr(self, name))
        _utc("canceled_at", self.canceled_at)
        if not isinstance(self.evidence_refs, tuple) or not self.evidence_refs:
            raise ValueError("cancellation requires immutable evidence refs")


@dataclass(frozen=True, slots=True)
class TrialConversionAssessment:
    status: TrialConversionStatus
    assessed_at: str
    agreement_id: str
    agreement_version: str
    pricing_plan_id: str
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, TrialConversionStatus):
            raise TypeError("status must be TrialConversionStatus")
        _utc("assessed_at", self.assessed_at)
        for name in (
            "agreement_id",
            "agreement_version",
            "pricing_plan_id",
            "reason",
        ):
            _canonical(name, getattr(self, name))

    @property
    def automatic_conversion_allowed(self) -> bool:
        return self.status == TrialConversionStatus.ELIGIBLE_TO_CONVERT

    @property
    def money_movement_allowed(self) -> bool:
        return False

    @property
    def payment_execution_allowed(self) -> bool:
        return False

    @property
    def execution_authority(self) -> bool:
        return False


def assess_trial_conversion(
    agreement: CommercialAgreementSnapshot,
    enrollment: TrialEnrollment,
    *,
    assessed_at: str,
    cancellation: TrialCancellation | None = None,
) -> TrialConversionAssessment:
    """Fail-closed automatic-conversion eligibility assessment.

    This establishes documentary eligibility only. It never creates payment
    authority or moves customer funds.
    """

    if not isinstance(agreement, CommercialAgreementSnapshot):
        raise TypeError("agreement must be CommercialAgreementSnapshot")
    if not isinstance(enrollment, TrialEnrollment):
        raise TypeError("enrollment must be TrialEnrollment")

    if (
        enrollment.agreement_id != agreement.agreement_id
        or enrollment.agreement_version != agreement.agreement_version
        or enrollment.pricing_plan_id != agreement.pricing_plan_id
    ):
        return TrialConversionAssessment(
            TrialConversionStatus.BLOCKED,
            assessed_at,
            agreement.agreement_id,
            agreement.agreement_version,
            agreement.pricing_plan_id,
            "accepted agreement/pricing snapshot does not match governing version",
        )

    if enrollment.displayed_pricing_summary != agreement.pricing_summary:
        return TrialConversionAssessment(
            TrialConversionStatus.BLOCKED,
            assessed_at,
            agreement.agreement_id,
            agreement.agreement_version,
            agreement.pricing_plan_id,
            "displayed pricing does not match governing agreement",
        )

    if (
        enrollment.displayed_conversion_disclosure
        != agreement.automatic_conversion_disclosure
    ):
        return TrialConversionAssessment(
            TrialConversionStatus.BLOCKED,
            assessed_at,
            agreement.agreement_id,
            agreement.agreement_version,
            agreement.pricing_plan_id,
            "automatic-conversion disclosure mismatch",
        )

    now = _utc("assessed_at", assessed_at)
    start = _utc("trial_start_at", enrollment.trial_start_at)
    expiry = _utc("trial_expires_at", enrollment.trial_expires_at)

    if cancellation is not None:
        if not isinstance(cancellation, TrialCancellation):
            raise TypeError("cancellation must be TrialCancellation")
        if (
            cancellation.customer_id != enrollment.customer_id
            or cancellation.account_reference != enrollment.account_reference
        ):
            return TrialConversionAssessment(
                TrialConversionStatus.BLOCKED,
                assessed_at,
                agreement.agreement_id,
                agreement.agreement_version,
                agreement.pricing_plan_id,
                "cancellation identity does not match trial enrollment",
            )
        canceled_at = _utc("canceled_at", cancellation.canceled_at)
        if canceled_at < expiry:
            return TrialConversionAssessment(
                TrialConversionStatus.CANCELED,
                assessed_at,
                agreement.agreement_id,
                agreement.agreement_version,
                agreement.pricing_plan_id,
                "customer canceled before trial expiry",
            )

    if now < start:
        status = TrialConversionStatus.NOT_STARTED
        reason = "trial has not started"
    elif now < expiry:
        status = TrialConversionStatus.TRIAL_ACTIVE
        reason = "trial remains active"
    else:
        status = TrialConversionStatus.ELIGIBLE_TO_CONVERT
        reason = "trial expired without a qualifying pre-expiry cancellation"

    return TrialConversionAssessment(
        status,
        assessed_at,
        agreement.agreement_id,
        agreement.agreement_version,
        agreement.pricing_plan_id,
        reason,
    )
