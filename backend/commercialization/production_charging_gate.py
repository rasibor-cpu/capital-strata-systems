from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple

from backend.commercialization.trial_contract import (
    TrialConversionAssessment,
    TrialConversionStatus,
)


class ProductionChargingGateError(ValueError):
    """Base error for production commercial charging controls."""


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True, slots=True)
class JurisdictionLegalReview:
    jurisdiction_code: str
    agreement_id: str
    agreement_version: str
    status: ApprovalStatus
    reviewed_at: str
    reviewer_reference: str
    evidence_refs: Tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "jurisdiction_code",
            "agreement_id",
            "agreement_version",
            "reviewed_at",
            "reviewer_reference",
        ):
            value = getattr(self, name)
            if not value or value != value.strip():
                raise ValueError(f"{name} is required and must be canonical")
        if not isinstance(self.status, ApprovalStatus):
            raise TypeError("status must be ApprovalStatus")
        if not isinstance(self.evidence_refs, tuple) or not self.evidence_refs:
            raise ValueError("legal review requires immutable evidence refs")


@dataclass(frozen=True, slots=True)
class ProductionCommercializationCertification:
    certification_id: str
    agreement_id: str
    agreement_version: str
    jurisdiction_code: str
    status: ApprovalStatus
    certified_at: str
    reconciliation_verified: bool
    security_release_blockers_clear: bool
    charging_controls_verified: bool
    evidence_refs: Tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "certification_id",
            "agreement_id",
            "agreement_version",
            "jurisdiction_code",
            "certified_at",
        ):
            value = getattr(self, name)
            if not value or value != value.strip():
                raise ValueError(f"{name} is required and must be canonical")
        if not isinstance(self.status, ApprovalStatus):
            raise TypeError("status must be ApprovalStatus")
        if not isinstance(self.evidence_refs, tuple) or not self.evidence_refs:
            raise ValueError("certification requires immutable evidence refs")


@dataclass(frozen=True, slots=True)
class PaymentCollectionAuthorityApproval:
    authority_id: str
    agreement_id: str
    agreement_version: str
    jurisdiction_code: str
    status: ApprovalStatus
    approved_at: str
    authority_reference: str
    evidence_refs: Tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "authority_id",
            "agreement_id",
            "agreement_version",
            "jurisdiction_code",
            "approved_at",
            "authority_reference",
        ):
            value = getattr(self, name)
            if not value or value != value.strip():
                raise ValueError(f"{name} is required and must be canonical")
        if not isinstance(self.status, ApprovalStatus):
            raise TypeError("status must be ApprovalStatus")
        if not isinstance(self.evidence_refs, tuple) or not self.evidence_refs:
            raise ValueError("payment authority requires immutable evidence refs")


@dataclass(frozen=True, slots=True)
class ProductionChargingAssessment:
    allowed: bool
    reason_codes: Tuple[str, ...]
    agreement_id: str
    agreement_version: str
    jurisdiction_code: str

    @property
    def client_funds_deduction_allowed(self) -> bool:
        return self.allowed

    @property
    def automatic_debit_allowed(self) -> bool:
        return self.allowed

    @property
    def payment_initiation_allowed(self) -> bool:
        return self.allowed

    @property
    def fee_collection_allowed(self) -> bool:
        return self.allowed

    @property
    def broker_execution_authority(self) -> bool:
        return False

    @property
    def trading_execution_authority(self) -> bool:
        return False

    @property
    def broker_withdrawal_allowed(self) -> bool:
        return False


def assess_production_charging(
    *,
    agreement_id: str,
    agreement_version: str,
    jurisdiction_code: str,
    contract_accepted: bool,
    trial_assessment: TrialConversionAssessment | None,
    legal_review: JurisdictionLegalReview | None,
    certification: ProductionCommercializationCertification | None,
    payment_authority: PaymentCollectionAuthorityApproval | None,
) -> ProductionChargingAssessment:
    """Conjunctive fail-closed production charging gate.

    This assessment does not itself execute a charge. It only determines
    whether a separately controlled payment/collection subsystem may be
    permitted to proceed.
    """

    reasons: list[str] = []

    if not contract_accepted:
        reasons.append("CONTRACT_NOT_ACCEPTED")

    if trial_assessment is None:
        reasons.append("TRIAL_ASSESSMENT_MISSING")
    elif not isinstance(trial_assessment, TrialConversionAssessment):
        raise TypeError("trial_assessment must be TrialConversionAssessment or None")
    elif trial_assessment.status != TrialConversionStatus.ELIGIBLE_TO_CONVERT:
        reasons.append("TRIAL_NOT_ELIGIBLE_FOR_PAID_SERVICE")

    if legal_review is None:
        reasons.append("LEGAL_REVIEW_MISSING")
    elif not isinstance(legal_review, JurisdictionLegalReview):
        raise TypeError("legal_review must be JurisdictionLegalReview or None")
    elif (
        legal_review.agreement_id != agreement_id
        or legal_review.agreement_version != agreement_version
        or legal_review.jurisdiction_code != jurisdiction_code
    ):
        reasons.append("LEGAL_REVIEW_SCOPE_MISMATCH")
    elif legal_review.status != ApprovalStatus.APPROVED:
        reasons.append("LEGAL_REVIEW_NOT_APPROVED")

    if certification is None:
        reasons.append("PRODUCTION_CERTIFICATION_MISSING")
    elif not isinstance(certification, ProductionCommercializationCertification):
        raise TypeError(
            "certification must be ProductionCommercializationCertification or None"
        )
    elif (
        certification.agreement_id != agreement_id
        or certification.agreement_version != agreement_version
        or certification.jurisdiction_code != jurisdiction_code
    ):
        reasons.append("CERTIFICATION_SCOPE_MISMATCH")
    else:
        if certification.status != ApprovalStatus.APPROVED:
            reasons.append("PRODUCTION_CERTIFICATION_NOT_APPROVED")
        if not certification.reconciliation_verified:
            reasons.append("RECONCILIATION_NOT_VERIFIED")
        if not certification.security_release_blockers_clear:
            reasons.append("SECURITY_RELEASE_BLOCKERS_ACTIVE")
        if not certification.charging_controls_verified:
            reasons.append("CHARGING_CONTROLS_NOT_VERIFIED")

    if payment_authority is None:
        reasons.append("PAYMENT_COLLECTION_AUTHORITY_MISSING")
    elif not isinstance(payment_authority, PaymentCollectionAuthorityApproval):
        raise TypeError(
            "payment_authority must be PaymentCollectionAuthorityApproval or None"
        )
    elif (
        payment_authority.agreement_id != agreement_id
        or payment_authority.agreement_version != agreement_version
        or payment_authority.jurisdiction_code != jurisdiction_code
    ):
        reasons.append("PAYMENT_AUTHORITY_SCOPE_MISMATCH")
    elif payment_authority.status != ApprovalStatus.APPROVED:
        reasons.append("PAYMENT_COLLECTION_AUTHORITY_NOT_APPROVED")

    return ProductionChargingAssessment(
        allowed=not reasons,
        reason_codes=tuple(reasons),
        agreement_id=agreement_id,
        agreement_version=agreement_version,
        jurisdiction_code=jurisdiction_code,
    )
