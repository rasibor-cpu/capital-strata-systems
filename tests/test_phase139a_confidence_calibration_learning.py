from backend.learning.confidence_calibration_learning import ConfidenceCalibrationLearningEngine


def test_confidence_calibration_learning_detects_optimism() -> None:
    result = ConfidenceCalibrationLearningEngine().analyze(
        [
            {"confidence": 90, "multi_factor_signal": {"multi_factor_score": 80}, "realized_return": -1.0},
            {"confidence": 80, "multi_factor_signal": {"multi_factor_score": 75}, "realized_return": 2.0},
        ]
    )

    assert result["status"] == "OK"
    assert result["calibration_bias"] == "OPTIMISTIC"
    assert result["calibration_learning_score"] < 100


def test_confidence_calibration_learning_missing_history_fails_closed() -> None:
    result = ConfidenceCalibrationLearningEngine().analyze([])

    assert result["status"] == "DATA UNAVAILABLE"
    assert result["calibration_bias"] == "DATA UNAVAILABLE"
