from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from backend.commercialization.production_charging_gate import (
    ProductionChargingAssessment,
)
from backend.commercialization.payment_collection_provider import (
    PaymentCollectionPreflight,
)


@dataclass(frozen=True, slots=True)
class CommercializationTechnicalValidation:
    validation_id: str
    commit_sha: str
    validated_at: str
    test_count: int
    full_regression_passed: bool
    governance_validation_passed: bool
    commercialization_consistency_passed: bool
    evidence_refs: Tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("validation_id", "commit_sha", "validated_at"):
            value = getattr(self, name)
            if not value or value != value.strip():
                raise ValueError(f"{name} is required and must be canonical")
        if self.test_count < 0:
            raise ValueError("test_count cannot be negative")
        if not isinstance(self.evidence_refs, tuple) or not self.evidence_refs:
            raise ValueError("technical validation requires immutable evidence refs")

    @property
    def passed(self) -> bool:
        return (
            self.full_regression_passed
            and self.governance_validation_passed
            and self.commercialization_consistency_passed
        )


@dataclass(frozen=True, slots=True)
class CommercializationReleaseAssessment:
    production_ready: bool
    reason_codes: Tuple[str, ...]
    validation_id: str | None
    validated_commit_sha: str | None
    charging_allowed: bool
    payment_provider_ready: bool

    @property
    def live_fee_collection_release_allowed(self) -> bool:
        return self.production_ready

    @property
    def trading_execution_authority(self) -> bool:
        return False

    @property
    def broker_execution_authority(self) -> bool:
        return False


def assess_commercialization_release(
    *,
    technical_validation: CommercializationTechnicalValidation | None,
    charging_assessment: ProductionChargingAssessment,
    payment_preflight: PaymentCollectionPreflight | None,
) -> CommercializationReleaseAssessment:
    reasons: list[str] = []

    if technical_validation is None:
        reasons.append("TECHNICAL_VALIDATION_MISSING")
    elif not isinstance(
        technical_validation,
        CommercializationTechnicalValidation,
    ):
        raise TypeError(
            "technical_validation must be CommercializationTechnicalValidation or None"
        )
    elif not technical_validation.passed:
        if not technical_validation.full_regression_passed:
            reasons.append("FULL_REGRESSION_NOT_PASSED")
        if not technical_validation.governance_validation_passed:
            reasons.append("GOVERNANCE_VALIDATION_NOT_PASSED")
        if not technical_validation.commercialization_consistency_passed:
            reasons.append("COMMERCIALIZATION_CONSISTENCY_NOT_PASSED")

    if not isinstance(charging_assessment, ProductionChargingAssessment):
        raise TypeError("charging_assessment must be ProductionChargingAssessment")

    if not charging_assessment.allowed:
        reasons.extend(
            f"CHARGING_GATE:{code}"
            for code in charging_assessment.reason_codes
        )

    if payment_preflight is None:
        reasons.append("PAYMENT_PROVIDER_PREFLIGHT_MISSING")
        payment_provider_ready = False
    elif not isinstance(payment_preflight, PaymentCollectionPreflight):
        raise TypeError(
            "payment_preflight must be PaymentCollectionPreflight or None"
        )
    else:
        payment_provider_ready = payment_preflight.allowed
        if not payment_preflight.allowed:
            reasons.extend(
                f"PAYMENT_PREFLIGHT:{code}"
                for code in payment_preflight.reason_codes
            )

    return CommercializationReleaseAssessment(
        production_ready=not reasons,
        reason_codes=tuple(dict.fromkeys(reasons)),
        validation_id=(
            technical_validation.validation_id
            if technical_validation is not None
            else None
        ),
        validated_commit_sha=(
            technical_validation.commit_sha
            if technical_validation is not None
            else None
        ),
        charging_allowed=charging_assessment.allowed,
        payment_provider_ready=payment_provider_ready,
    )
