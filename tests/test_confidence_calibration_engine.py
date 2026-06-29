from __future__ import annotations

from backend.portfolio.confidence_calibration_engine import ConfidenceCalibrationEngine


def test_confidence_calibration_engine_builds_buckets_and_curve() -> None:
    history = [
        {"confidence": 0.8, "hit": True, "outcome": {"realized_return": 0.03}},
        {"confidence": 0.75, "hit": True, "outcome": {"realized_return": 0.02}},
        {"confidence": 0.25, "hit": False, "outcome": {"realized_return": -0.01}},
        {"confidence": 0.2, "hit": False, "outcome": {"realized_return": -0.02}},
    ]

    result = ConfidenceCalibrationEngine().analyze(history)

    assert result["status"] == "OK"
    assert result["calibration_status"] == "WELL_CALIBRATED"
    assert result["calibration_score"] == 77.5
    assert result["expected_vs_actual"]["expected_confidence"] == 50.0
    assert result["expected_vs_actual"]["actual_accuracy"] == 50.0
    assert result["confidence_buckets"]["20-40"]["count"] == 2
    assert result["confidence_buckets"]["60-80"]["actual_accuracy"] == 100.0
    assert result["advisory_only"] is True
    assert result["execution_allowed"] is False


def test_confidence_calibration_engine_detects_optimism() -> None:
    result = ConfidenceCalibrationEngine().analyze(
        [
            {"confidence": 0.9, "hit": False},
            {"confidence": 0.8, "hit": False},
        ]
    )

    assert result["status"] == "OK"
    assert result["calibration_status"] == "OPTIMISTIC"
    assert result["calibration_score"] < 25.0


def test_confidence_calibration_engine_fails_closed_without_history() -> None:
    result = ConfidenceCalibrationEngine().analyze([{"recommendation": "MAINTAIN"}])

    assert result["status"] == "DATA UNAVAILABLE"
    assert result["calibration_score"] is None
    assert result["confidence_buckets"] == {}
