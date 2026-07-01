from backend.learning.engine_health_learning import EngineHealthLearningEngine


def test_engine_health_learning_green_when_packages_ok() -> None:
    result = EngineHealthLearningEngine().evaluate(
        {
            "factor_performance": {"status": "OK"},
            "factor_attribution": {"status": "OK"},
            "rolling_reliability": {"status": "OK"},
        }
    )

    assert result["status"] == "OK"
    assert result["learning_health_status"] == "GREEN"
    assert result["blockers"] == []


def test_engine_health_learning_reports_partial_and_unavailable() -> None:
    result = EngineHealthLearningEngine().evaluate(
        {
            "factor_performance": {"status": "PARTIAL"},
            "factor_attribution": {"status": "DATA UNAVAILABLE"},
        }
    )

    assert result["learning_health_status"] == "AMBER"
    assert "factor_attribution_unavailable" in result["blockers"]
    assert "factor_performance_partial" in result["warnings"]
