from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from backend.learning.common import confidence, hit, outcome, rows, unavailable
from backend.portfolio.utils import advisory_response


class ConfidenceCalibrationLearningEngine:
    """Learn whether advisory confidence has been optimistic or conservative."""

    def analyze(self, history: Iterable[Mapping[str, Any]] | None, *, bucket_size: int = 20) -> dict[str, Any]:
        buckets: dict[str, list[dict[str, float]]] = {}
        safe_bucket = max(5, min(50, int(bucket_size or 20)))
        for row in rows(history):
            conf = confidence(row)
            realized = outcome(row)
            if conf is None or realized is None:
                continue
            score = 50.0
            if isinstance(row.get("multi_factor_signal"), Mapping):
                score = float(row["multi_factor_signal"].get("multi_factor_score", score) or score)
            label_start = min(100 - safe_bucket, max(0, int(conf * 100.0 // safe_bucket) * safe_bucket))
            label = f"{label_start}-{label_start + safe_bucket}"
            buckets.setdefault(label, []).append({"confidence": conf, "hit": 1.0 if hit(score, realized) else 0.0})

        if not buckets:
            return unavailable(
                "confidence_calibration_learning_history_unavailable",
                calibration_buckets={},
                calibration_bias="DATA UNAVAILABLE",
                calibration_learning_score=None,
            )

        bucket_payload: dict[str, dict[str, Any]] = {}
        total_gap = 0.0
        total_count = 0
        expected_sum = 0.0
        actual_sum = 0.0
        for label, values in sorted(buckets.items(), key=lambda item: int(item[0].split("-", 1)[0])):
            count = len(values)
            expected = sum(item["confidence"] for item in values) / count
            actual = sum(item["hit"] for item in values) / count
            gap = actual - expected
            total_gap += abs(gap) * count
            total_count += count
            expected_sum += expected * count
            actual_sum += actual * count
            bucket_payload[label] = {
                "sample_size": count,
                "expected_confidence": round(expected * 100.0, 6),
                "actual_accuracy": round(actual * 100.0, 6),
                "calibration_gap": round(gap * 100.0, 6),
            }

        expected_avg = expected_sum / total_count
        actual_avg = actual_sum / total_count
        bias = "OPTIMISTIC" if expected_avg - actual_avg > 0.1 else "CONSERVATIVE" if actual_avg - expected_avg > 0.1 else "WELL_CALIBRATED"
        return advisory_response(
            "OK",
            calibration_buckets=bucket_payload,
            calibration_bias=bias,
            calibration_learning_score=round(max(0.0, 100.0 - (total_gap / total_count) * 100.0), 6),
            expected_confidence=round(expected_avg * 100.0, 6),
            actual_accuracy=round(actual_avg * 100.0, 6),
            recommended_actions=[self._action(bias)],
        )

    @staticmethod
    def _action(bias: str) -> str:
        if bias == "OPTIMISTIC":
            return "Reduce advisory confidence until realized accuracy catches up."
        if bias == "CONSERVATIVE":
            return "Confidence appears conservative; review whether stronger advisory language is warranted."
        return "Maintain current deterministic confidence calibration."
