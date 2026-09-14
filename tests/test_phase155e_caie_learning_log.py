from datetime import datetime, timezone
from decimal import Decimal

from backend.allocation.caie_learning_log import (
    CAIELearningLog,
    CAIEOutcomeRecord,
    CAIERecommendationRecord,
)
from backend.allocation.caie_outcome_calibration import summarize_calibration


NOW = datetime(2026, 9, 15, 0, 20, tzinfo=timezone.utc)


def recommendation(proposal_id, ev="0.05", confidence="0.70"):
    return CAIERecommendationRecord(
        proposal_id=proposal_id,
        expected_value_pct=Decimal(ev),
        confidence=Decimal(confidence),
        recommended_capital=Decimal("500"),
        recorded_at_utc=NOW,
    )


def outcome(proposal_id, realized="0.04"):
    return CAIEOutcomeRecord(
        proposal_id=proposal_id,
        realized_return_pct=Decimal(realized),
        closed_at_utc=NOW,
    )


def test_closed_trade_outcome_matches_recommendation_by_proposal_id():
    log = CAIELearningLog()
    assert log.record_recommendation(recommendation("opp-1")) is True
    assert log.record_outcome(outcome("opp-1")) is True
    matched = log.matched_outcomes()
    assert len(matched) == 1
    assert matched[0].recommendation.proposal_id == "opp-1"
    assert matched[0].outcome.proposal_id == "opp-1"


def test_duplicate_records_are_idempotently_rejected():
    log = CAIELearningLog()
    assert log.record_recommendation(recommendation("opp-1")) is True
    assert log.record_recommendation(recommendation("opp-1")) is False
    assert log.record_outcome(outcome("opp-1")) is True
    assert log.record_outcome(outcome("opp-1")) is False
    assert log.snapshot()["matched_count"] == 1


def test_expected_vs_actual_ev_is_calculated():
    log = CAIELearningLog()
    log.record_recommendation(recommendation("a", ev="0.06"))
    log.record_recommendation(recommendation("b", ev="0.02"))
    log.record_outcome(outcome("a", realized="0.04"))
    log.record_outcome(outcome("b", realized="-0.01"))

    summary = summarize_calibration(log.matched_outcomes())
    assert summary.matched_count == 2
    assert summary.mean_expected_value_pct == Decimal("0.040000")
    assert summary.mean_actual_return_pct == Decimal("0.015000")
    assert summary.expected_minus_actual_pct == Decimal("0.025000")


def test_confidence_calibration_is_summarized():
    log = CAIELearningLog()
    log.record_recommendation(recommendation("a", confidence="0.80"))
    log.record_recommendation(recommendation("b", confidence="0.60"))
    log.record_outcome(outcome("a", realized="0.01"))
    log.record_outcome(outcome("b", realized="-0.01"))

    summary = summarize_calibration(log.matched_outcomes())
    assert summary.mean_confidence == Decimal("0.700000")
    assert summary.realized_win_rate == Decimal("0.500000")
    assert summary.confidence_minus_win_rate == Decimal("0.200000")


def test_unmatched_records_are_not_used_for_calibration():
    log = CAIELearningLog()
    log.record_recommendation(recommendation("only-rec"))
    assert summarize_calibration(log.matched_outcomes()).matched_count == 0


def test_learning_log_is_advisory_only():
    log = CAIELearningLog()
    snapshot = log.snapshot()
    assert snapshot["mode"] == "SHADOW_ONLY"
    assert snapshot["automated_learning_enabled"] is False
    assert snapshot["execution_allowed"] is False
    assert not hasattr(log, "place_order")
    assert not hasattr(log, "update_live_weights")
