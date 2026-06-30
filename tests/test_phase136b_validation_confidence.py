from backend.validation.validation_confidence_engine import ValidationConfidenceEngine


def test_validation_confidence_high_for_green_signals() -> None:
    result = ValidationConfidenceEngine().evaluate(
        runtime_health={"runtime_health": "GREEN"},
        validation_readiness={"readiness_status": "READY"},
        artifact_freshness={"freshness_status": "GREEN"},
        supervisor_stability={"restart_count": 0, "recovery_count": 0},
        session_continuity={"session_continuity_status": "ACTIVE"},
        recommendation_stability={"recommendation_stability": "STABLE"},
        portfolio_decision={"overall_status": "GREEN"},
        runtime_health_trend={"trends": {"1h": {"degradation_count": 0}}},
    )

    assert result["confidence_score"] == 100
    assert result["confidence_grade"] == "HIGH"


def test_validation_confidence_fails_closed_for_unknowns() -> None:
    result = ValidationConfidenceEngine().evaluate(
        runtime_health=None,
        validation_readiness={"readiness_status": "NOT_READY"},
        artifact_freshness=None,
        session_continuity={"session_continuity_status": "EXPIRED"},
        portfolio_decision={"overall_status": "RED"},
    )

    assert result["confidence_grade"] == "FAIL_CLOSED"
    assert result["execution_allowed"] is False
