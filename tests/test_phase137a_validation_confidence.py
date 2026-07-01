from backend.validation.validation_confidence_engine import ValidationConfidenceEngine


def _confidence(**overrides):
    payload = {
        "runtime_health": {"runtime_health": "GREEN"},
        "validation_readiness": {"readiness_status": "READY"},
        "artifact_freshness": {"freshness_status": "GREEN"},
        "supervisor_stability": {"restart_count": 0, "recovery_count": 0},
        "session_continuity": {"session_continuity_status": "ACTIVE"},
        "portfolio_decision": {"overall_status": "GREEN"},
        "advisory_snapshot": {"snapshot_status": "OK", "missing_components": []},
        "runtime_health_trend": {"trends": {"1h": {"degradation_count": 0}}},
    }
    payload.update(overrides)
    return ValidationConfidenceEngine().evaluate(**payload)


def test_phase137a_confidence_healthy_runtime_scores_high() -> None:
    result = _confidence()

    assert 80 <= result["confidence_score"] <= 100
    assert result["confidence_grade"] == "HIGH"


def test_phase137a_confidence_minor_degradation_scores_60_to_80() -> None:
    result = _confidence(runtime_health={"runtime_health": "AMBER"})

    assert 60 <= result["confidence_score"] <= 80


def test_phase137a_confidence_operational_degradation_scores_40_to_60() -> None:
    result = _confidence(
        runtime_health={"runtime_health": "AMBER"},
        validation_readiness={"readiness_status": "READY_WITH_CAUTION"},
        artifact_freshness={"freshness_status": "AMBER"},
    )

    assert 40 <= result["confidence_score"] <= 60


def test_phase137a_confidence_critical_failures_score_0_to_40() -> None:
    result = _confidence(
        runtime_health={"runtime_health": "RED"},
        validation_readiness={"readiness_status": "NOT_READY"},
        artifact_freshness={"freshness_status": "RED"},
        session_continuity={"session_continuity_status": "EXPIRED"},
        portfolio_decision={"overall_status": "RED"},
    )

    assert 0 <= result["confidence_score"] <= 40
    assert result["execution_allowed"] is False
