from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class CAIEPromotionStage(str, Enum):
    SHADOW_ONLY = "SHADOW_ONLY"
    ACTIVE_ADVISORY_10 = "ACTIVE_ADVISORY_10"
    ACTIVE_ADVISORY_25 = "ACTIVE_ADVISORY_25"
    ACTIVE_ADVISORY_50 = "ACTIVE_ADVISORY_50"
    ACTIVE_ALLOCATION_100 = "ACTIVE_ALLOCATION_100"


_STAGE_ORDER = (
    CAIEPromotionStage.SHADOW_ONLY,
    CAIEPromotionStage.ACTIVE_ADVISORY_10,
    CAIEPromotionStage.ACTIVE_ADVISORY_25,
    CAIEPromotionStage.ACTIVE_ADVISORY_50,
    CAIEPromotionStage.ACTIVE_ALLOCATION_100,
)


@dataclass(frozen=True)
class CAIEPromotionMetrics:
    matched_outcomes: int
    absolute_ev_calibration_error: Decimal
    absolute_confidence_calibration_error: Decimal

    def __post_init__(self) -> None:
        if self.matched_outcomes < 0:
            raise ValueError("matched_outcomes must be non-negative")
        for value in (
            self.absolute_ev_calibration_error,
            self.absolute_confidence_calibration_error,
        ):
            if value < 0 or not value.is_finite():
                raise ValueError("calibration errors must be finite and non-negative")


@dataclass(frozen=True)
class CAIEPromotionThresholds:
    minimum_matched_outcomes: int = 30
    maximum_ev_calibration_error: Decimal = Decimal("0.05")
    maximum_confidence_calibration_error: Decimal = Decimal("0.20")

    def __post_init__(self) -> None:
        if self.minimum_matched_outcomes <= 0:
            raise ValueError("minimum_matched_outcomes must be positive")
        if self.maximum_ev_calibration_error < 0:
            raise ValueError("maximum_ev_calibration_error must be non-negative")
        if self.maximum_confidence_calibration_error < 0:
            raise ValueError("maximum_confidence_calibration_error must be non-negative")


@dataclass(frozen=True)
class CAIEPromotionDecision:
    current_stage: CAIEPromotionStage
    requested_stage: CAIEPromotionStage
    effective_stage: CAIEPromotionStage
    status: str
    reason_codes: tuple[str, ...]
    metrics_sufficient: bool
    execution_allowed: bool = False
    broker_execution_armed: bool = False
    money_movement_allowed: bool = False
    live_trading_authorized: bool = False


def _metrics_sufficient(
    metrics: CAIEPromotionMetrics,
    thresholds: CAIEPromotionThresholds,
) -> tuple[bool, tuple[str, ...]]:
    reasons: list[str] = []
    if metrics.matched_outcomes < thresholds.minimum_matched_outcomes:
        reasons.append("INSUFFICIENT_MATCHED_OUTCOMES")
    if metrics.absolute_ev_calibration_error > thresholds.maximum_ev_calibration_error:
        reasons.append("EV_CALIBRATION_ERROR_TOO_HIGH")
    if (
        metrics.absolute_confidence_calibration_error
        > thresholds.maximum_confidence_calibration_error
    ):
        reasons.append("CONFIDENCE_CALIBRATION_ERROR_TOO_HIGH")
    return not reasons, tuple(reasons)


def evaluate_caie_promotion(
    *,
    current_stage: CAIEPromotionStage = CAIEPromotionStage.SHADOW_ONLY,
    requested_stage: CAIEPromotionStage = CAIEPromotionStage.SHADOW_ONLY,
    metrics: CAIEPromotionMetrics,
    thresholds: CAIEPromotionThresholds | None = None,
    operator_approved: bool = False,
    governance_approved: bool = False,
    rollback_requested: bool = False,
) -> CAIEPromotionDecision:
    """Evaluate CAIE promotion without granting any broker/execution authority.

    Stage labels describe the maturity/visibility policy for CAIE recommendations.
    They are never order authority and never bypass canonical CSS gates.
    """

    thresholds = thresholds or CAIEPromotionThresholds()
    sufficient, metric_reasons = _metrics_sufficient(metrics, thresholds)

    if rollback_requested:
        return CAIEPromotionDecision(
            current_stage=current_stage,
            requested_stage=requested_stage,
            effective_stage=CAIEPromotionStage.SHADOW_ONLY,
            status="ROLLED_BACK",
            reason_codes=("ROLLBACK_REQUESTED",),
            metrics_sufficient=sufficient,
        )

    current_index = _STAGE_ORDER.index(current_stage)
    requested_index = _STAGE_ORDER.index(requested_stage)

    if requested_stage == current_stage:
        return CAIEPromotionDecision(
            current_stage=current_stage,
            requested_stage=requested_stage,
            effective_stage=current_stage,
            status="NO_CHANGE",
            reason_codes=("STAGE_UNCHANGED",),
            metrics_sufficient=sufficient,
        )

    if requested_index < current_index:
        # Any de-escalation is allowed as a safe reduction in CAIE influence.
        return CAIEPromotionDecision(
            current_stage=current_stage,
            requested_stage=requested_stage,
            effective_stage=requested_stage,
            status="DEESCALATED",
            reason_codes=("SAFE_DEESCALATION",),
            metrics_sufficient=sufficient,
        )

    reasons: list[str] = list(metric_reasons)
    if requested_index != current_index + 1:
        reasons.append("STAGE_SKIP_NOT_ALLOWED")
    if not operator_approved:
        reasons.append("OPERATOR_APPROVAL_REQUIRED")
    if not governance_approved:
        reasons.append("GOVERNANCE_APPROVAL_REQUIRED")

    if reasons:
        return CAIEPromotionDecision(
            current_stage=current_stage,
            requested_stage=requested_stage,
            effective_stage=current_stage,
            status="BLOCKED",
            reason_codes=tuple(reasons),
            metrics_sufficient=sufficient,
        )

    return CAIEPromotionDecision(
        current_stage=current_stage,
        requested_stage=requested_stage,
        effective_stage=requested_stage,
        status="APPROVED_POLICY_STAGE",
        reason_codes=("EXPLICIT_APPROVALS_PRESENT", "METRICS_GATE_PASSED"),
        metrics_sufficient=True,
    )
