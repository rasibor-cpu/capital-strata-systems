from backend.learning.rolling_reliability import RollingReliabilityEngine


def test_rolling_reliability_tracks_latest_factor_hit_rate() -> None:
    history = [
        {"factor_scores": {"technical": 80, "fundamental": 20}, "realized_return": 1.0},
        {"factor_scores": {"technical": 75, "fundamental": 25}, "realized_return": 2.0},
        {"factor_scores": {"technical": 30, "fundamental": 65}, "realized_return": -1.0},
    ]

    result = RollingReliabilityEngine().evaluate(history, window=2)

    assert result["status"] == "PARTIAL"
    assert result["latest_reliability"]["technical"] == 100.0
    assert result["reliability_status"] == "DEGRADED"


def test_rolling_reliability_missing_history_fails_closed() -> None:
    result = RollingReliabilityEngine().evaluate([])

    assert result["status"] == "DATA UNAVAILABLE"
    assert result["reliability_status"] == "DATA UNAVAILABLE"
