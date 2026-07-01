from backend.learning.factor_performance import FactorPerformanceEngine


def _history() -> list[dict]:
    return [
        {"factor_scores": {"technical": 80, "fundamental": 45, "sentiment": 70, "quantitative": 75}, "realized_return": 4.0},
        {"factor_scores": {"technical": 30, "fundamental": 65, "sentiment": 35, "quantitative": 40}, "realized_return": -2.0},
        {"factor_scores": {"technical": 70, "fundamental": 55, "sentiment": 60, "quantitative": 72}, "realized_return": 3.0},
    ]


def test_factor_performance_scores_factor_reliability() -> None:
    result = FactorPerformanceEngine().analyze(_history())

    assert result["status"] == "OK"
    assert result["factors"]["technical"]["sample_size"] == 3
    assert result["factors"]["technical"]["hit_rate"] == 100.0
    assert result["best_factor"] in {"technical", "sentiment", "quantitative"}
    assert result["advisory_only"] is True
    assert result["execution_allowed"] is False


def test_factor_performance_missing_history_fails_closed() -> None:
    result = FactorPerformanceEngine().analyze([])

    assert result["status"] == "DATA UNAVAILABLE"
    assert result["best_factor"] == "DATA UNAVAILABLE"
