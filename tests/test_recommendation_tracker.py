from __future__ import annotations

import os

from backend.portfolio.recommendation_tracker import RecommendationTracker


def test_recommendation_tracker_persists_and_evaluates(tmp_path) -> None:
    tracker = RecommendationTracker(str(tmp_path))
    recorded = tracker.record_recommendation({"adaptive_recommendation": "REDUCE_RISK"})

    assert recorded["status"] == "OK"
    recommendation_id = recorded["record"]["id"]
    evaluation = tracker.evaluate_outcome(recommendation_id, {"realized_return": -0.03, "max_drawdown": 0.08})
    summary = tracker.summary()

    assert evaluation["status"] == "OK"
    assert evaluation["evaluation"]["hit"] is True
    assert summary["total_recommendations"] == 1
    assert summary["evaluated_recommendations"] == 1
    assert summary["hit_rate"] == 100.0


def test_recommendation_tracker_handles_missing_and_corrupt_json(tmp_path) -> None:
    tracker = RecommendationTracker(str(tmp_path))
    assert tracker.summary()["total_recommendations"] == 0

    os.makedirs(tmp_path, exist_ok=True)
    with open(tracker.path, "w", encoding="utf-8") as handle:
        handle.write("{bad json")

    assert tracker.summary()["total_recommendations"] == 0
    recorded = tracker.record_recommendation({"recommendation": "MAINTAIN"})
    assert recorded["count"] == 1


def test_recommendation_tracker_malformed_snapshot_is_safe(tmp_path) -> None:
    tracker = RecommendationTracker(str(tmp_path))
    result = tracker.record_recommendation("bad")

    assert result["status"] == "DATA UNAVAILABLE"
    assert result["advisory_only"] is True
