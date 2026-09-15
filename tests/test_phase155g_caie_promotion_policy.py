from decimal import Decimal

from backend.allocation.caie_promotion_policy import (
    CAIEPromotionMetrics,
    CAIEPromotionStage,
    CAIEPromotionThresholds,
    evaluate_caie_promotion,
)


def healthy_metrics():
    return CAIEPromotionMetrics(
        matched_outcomes=50,
        absolute_ev_calibration_error=Decimal("0.02"),
        absolute_confidence_calibration_error=Decimal("0.10"),
    )


def test_default_stage_is_shadow_only_and_no_change():
    decision = evaluate_caie_promotion(metrics=healthy_metrics())
    assert decision.current_stage == CAIEPromotionStage.SHADOW_ONLY
    assert decision.effective_stage == CAIEPromotionStage.SHADOW_ONLY
    assert decision.status == "NO_CHANGE"
    assert decision.execution_allowed is False
    assert decision.broker_execution_armed is False
    assert decision.money_movement_allowed is False
    assert decision.live_trading_authorized is False


def test_promotion_requires_explicit_operator_and_governance_approval():
    decision = evaluate_caie_promotion(
        current_stage=CAIEPromotionStage.SHADOW_ONLY,
        requested_stage=CAIEPromotionStage.ACTIVE_ADVISORY_10,
        metrics=healthy_metrics(),
    )
    assert decision.status == "BLOCKED"
    assert decision.effective_stage == CAIEPromotionStage.SHADOW_ONLY
    assert "OPERATOR_APPROVAL_REQUIRED" in decision.reason_codes
    assert "GOVERNANCE_APPROVAL_REQUIRED" in decision.reason_codes


def test_insufficient_metrics_block_promotion_even_with_approvals():
    metrics = CAIEPromotionMetrics(
        matched_outcomes=5,
        absolute_ev_calibration_error=Decimal("0.20"),
        absolute_confidence_calibration_error=Decimal("0.50"),
    )
    decision = evaluate_caie_promotion(
        requested_stage=CAIEPromotionStage.ACTIVE_ADVISORY_10,
        metrics=metrics,
        operator_approved=True,
        governance_approved=True,
    )
    assert decision.status == "BLOCKED"
    assert decision.metrics_sufficient is False
    assert decision.effective_stage == CAIEPromotionStage.SHADOW_ONLY


def test_only_one_step_promotion_is_permitted():
    decision = evaluate_caie_promotion(
        current_stage=CAIEPromotionStage.SHADOW_ONLY,
        requested_stage=CAIEPromotionStage.ACTIVE_ADVISORY_50,
        metrics=healthy_metrics(),
        operator_approved=True,
        governance_approved=True,
    )
    assert decision.status == "BLOCKED"
    assert "STAGE_SKIP_NOT_ALLOWED" in decision.reason_codes


def test_valid_one_step_advisory_promotion_is_policy_only():
    decision = evaluate_caie_promotion(
        current_stage=CAIEPromotionStage.SHADOW_ONLY,
        requested_stage=CAIEPromotionStage.ACTIVE_ADVISORY_10,
        metrics=healthy_metrics(),
        operator_approved=True,
        governance_approved=True,
    )
    assert decision.status == "APPROVED_POLICY_STAGE"
    assert decision.effective_stage == CAIEPromotionStage.ACTIVE_ADVISORY_10
    assert decision.execution_allowed is False
    assert decision.broker_execution_armed is False
    assert decision.money_movement_allowed is False
    assert decision.live_trading_authorized is False


def test_active_allocation_100_label_never_grants_execution_authority():
    decision = evaluate_caie_promotion(
        current_stage=CAIEPromotionStage.ACTIVE_ADVISORY_50,
        requested_stage=CAIEPromotionStage.ACTIVE_ALLOCATION_100,
        metrics=healthy_metrics(),
        operator_approved=True,
        governance_approved=True,
    )
    assert decision.status == "APPROVED_POLICY_STAGE"
    assert decision.effective_stage == CAIEPromotionStage.ACTIVE_ALLOCATION_100
    assert decision.execution_allowed is False
    assert decision.broker_execution_armed is False
    assert decision.money_movement_allowed is False
    assert decision.live_trading_authorized is False


def test_rollback_returns_immediately_to_shadow_only():
    decision = evaluate_caie_promotion(
        current_stage=CAIEPromotionStage.ACTIVE_ALLOCATION_100,
        requested_stage=CAIEPromotionStage.ACTIVE_ALLOCATION_100,
        metrics=healthy_metrics(),
        rollback_requested=True,
    )
    assert decision.status == "ROLLED_BACK"
    assert decision.effective_stage == CAIEPromotionStage.SHADOW_ONLY


def test_safe_deescalation_does_not_require_promotion_approval():
    decision = evaluate_caie_promotion(
        current_stage=CAIEPromotionStage.ACTIVE_ADVISORY_50,
        requested_stage=CAIEPromotionStage.ACTIVE_ADVISORY_10,
        metrics=healthy_metrics(),
    )
    assert decision.status == "DEESCALATED"
    assert decision.effective_stage == CAIEPromotionStage.ACTIVE_ADVISORY_10


def test_custom_thresholds_are_enforced():
    thresholds = CAIEPromotionThresholds(
        minimum_matched_outcomes=100,
        maximum_ev_calibration_error=Decimal("0.01"),
        maximum_confidence_calibration_error=Decimal("0.05"),
    )
    decision = evaluate_caie_promotion(
        requested_stage=CAIEPromotionStage.ACTIVE_ADVISORY_10,
        metrics=healthy_metrics(),
        thresholds=thresholds,
        operator_approved=True,
        governance_approved=True,
    )
    assert decision.status == "BLOCKED"
    assert decision.metrics_sufficient is False
