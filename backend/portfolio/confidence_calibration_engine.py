from __future__ import annotations

from typing import Any, Iterable, Mapping

from backend.portfolio.utils import advisory_response, clamp, safe_float


class ConfidenceCalibrationEngineError(RuntimeError):
    """Fail-closed exception for confidence calibration analytics."""


class ConfidenceCalibrationEngine:
    """Deterministic confidence calibration for advisory recommendations."""

    def analyze(self, history: Iterable[Mapping[str, Any]] | None, *, bucket_size: int = 20) -> dict[str, Any]:
        rows = self._evaluable_rows(history)
        if not rows:
            return advisory_response(
                "DATA UNAVAILABLE",
                calibration_status="DATA UNAVAILABLE",
                calibration_score=None,
                calibration_curve=[],
                confidence_buckets={},
                expected_vs_actual={},
                recommendation="Insufficient evaluated recommendation history.",
            )

        safe_bucket = max(5, min(50, int(bucket_size or 20)))
        buckets: dict[str, list[dict[str, float]]] = {}
        total_gap = 0.0
        total_count = 0
        confidence_sum = 0.0
        hit_sum = 0.0
        performance_sum = 0.0

        for row in rows:
            confidence = row["confidence"]
            hit = 1.0 if row["hit"] else 0.0
            performance = row["performance"]
            bucket_start = int(confidence * 100.0 // safe_bucket) * safe_bucket
            bucket_start = min(100 - safe_bucket, max(0, bucket_start))
            label = f"{bucket_start}-{bucket_start + safe_bucket}"
            buckets.setdefault(label, []).append(
                {"confidence": confidence, "hit": hit, "performance": performance}
            )
            confidence_sum += confidence
            hit_sum += hit
            performance_sum += performance

        confidence_buckets: dict[str, dict[str, float | int]] = {}
        calibration_curve: list[dict[str, float | int | str]] = []
        for label in sorted(buckets.keys(), key=lambda item: int(item.split("-", 1)[0])):
            bucket_rows = buckets[label]
            count = len(bucket_rows)
            expected = sum(item["confidence"] for item in bucket_rows) / count
            actual = sum(item["hit"] for item in bucket_rows) / count
            performance = sum(item["performance"] for item in bucket_rows) / count
            gap = abs(expected - actual)
            total_gap += gap * count
            total_count += count
            bucket_payload = {
                "count": count,
                "expected_confidence": round(expected * 100.0, 6),
                "actual_accuracy": round(actual * 100.0, 6),
                "average_performance": round(performance, 6),
                "calibration_gap": round(gap * 100.0, 6),
            }
            confidence_buckets[label] = bucket_payload
            calibration_curve.append({"bucket": label, **bucket_payload})

        average_confidence = confidence_sum / len(rows)
        actual_accuracy = hit_sum / len(rows)
        average_performance = performance_sum / len(rows)
        weighted_gap = total_gap / total_count if total_count else 1.0
        calibration_score = round(max(0.0, 100.0 - (weighted_gap * 100.0)), 6)
        if average_confidence - actual_accuracy > 0.1:
            calibration_status = "OPTIMISTIC"
            recommendation = "Lower advisory confidence or require stronger confirming evidence."
        elif actual_accuracy - average_confidence > 0.1:
            calibration_status = "PESSIMISTIC"
            recommendation = "Confidence appears conservative relative to observed outcomes."
        else:
            calibration_status = "WELL_CALIBRATED"
            recommendation = "Maintain current deterministic confidence policy."

        return advisory_response(
            "OK",
            calibration_status=calibration_status,
            calibration_score=calibration_score,
            calibration_curve=calibration_curve,
            confidence_buckets=confidence_buckets,
            expected_vs_actual={
                "expected_confidence": round(average_confidence * 100.0, 6),
                "actual_accuracy": round(actual_accuracy * 100.0, 6),
                "average_performance": round(average_performance, 6),
                "sample_size": len(rows),
            },
            recommendation=recommendation,
        )

    @staticmethod
    def _evaluable_rows(history: Iterable[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
        if history is None or isinstance(history, (str, bytes)):
            return []
        rows: list[dict[str, Any]] = []
        try:
            iterator = iter(history)
        except TypeError:
            return []
        for item in iterator:
            if not isinstance(item, Mapping):
                continue
            confidence = ConfidenceCalibrationEngine._confidence(item)
            hit = ConfidenceCalibrationEngine._hit(item)
            if confidence is None or hit is None:
                continue
            rows.append(
                {
                    "confidence": confidence,
                    "hit": hit,
                    "performance": ConfidenceCalibrationEngine._performance(item),
                }
            )
        return rows

    @staticmethod
    def _confidence(row: Mapping[str, Any]) -> float | None:
        value = row.get("confidence", row.get("recommendation_confidence"))
        if value is None and isinstance(row.get("evaluation"), Mapping):
            value = row["evaluation"].get("confidence")
        if value is None:
            return None
        numeric = safe_float(value, -1.0)
        if numeric > 1.0:
            numeric /= 100.0
        if numeric < 0.0:
            return None
        return clamp(numeric, 0.0, 1.0)

    @staticmethod
    def _hit(row: Mapping[str, Any]) -> bool | None:
        if row.get("hit") is not None:
            return bool(row.get("hit"))
        evaluation = row.get("evaluation")
        if isinstance(evaluation, Mapping) and evaluation.get("hit") is not None:
            return bool(evaluation.get("hit"))
        outcome = row.get("outcome")
        if isinstance(outcome, Mapping) and outcome.get("hit") is not None:
            return bool(outcome.get("hit"))
        return None

    @staticmethod
    def _performance(row: Mapping[str, Any]) -> float:
        outcome = row.get("outcome")
        if isinstance(outcome, Mapping):
            return safe_float(
                outcome.get(
                    "realized_return",
                    outcome.get("forward_return", outcome.get("return", outcome.get("realized_pnl", 0.0))),
                )
            )
        return safe_float(row.get("realized_return", row.get("forward_return", row.get("return", 0.0))))
