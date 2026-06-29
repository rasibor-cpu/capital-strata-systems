from __future__ import annotations

from backend.validation.validation_readiness_engine import ValidationReadinessEngine


def test_validation_readiness_ready_case() -> None:
    result = ValidationReadinessEngine().evaluate(
        runtime_health={"runtime_health": "GREEN"},
        session_validation={"session_status": "GREEN"},
        portfolio_decision={"overall_status": "GREEN"},
        operational_telemetry={"overall_status": "GREEN"},
        stale_artifacts=[],
        recent_errors=[],
    )

    assert result["readiness_status"] == "READY"
    assert result["confidence"] == 100
    assert result["blockers"] == []
    assert result["warnings"] == []
    assert result["advisory_only"] is True
    assert result["execution_allowed"] is False


def test_validation_readiness_caution_case() -> None:
    result = ValidationReadinessEngine().evaluate(
        runtime_health={"runtime_health": "AMBER"},
        session_validation={"session_status": "GREEN"},
        portfolio_decision={"overall_status": "GREEN"},
        operational_telemetry={"overall_status": "AMBER"},
        stale_artifacts=["css_session_state_pcnrass.json"],
        recent_errors=["transient_api_error"],
    )

    assert result["readiness_status"] == "READY_WITH_CAUTION"
    assert result["confidence"] == 60
    assert "runtime_health_degraded" in result["warnings"]
    assert "stale_artifacts_present" in result["warnings"]
    assert result["blockers"] == []


def test_validation_readiness_not_ready_case() -> None:
    result = ValidationReadinessEngine().evaluate(
        runtime_health={"runtime_health": "RED"},
        session_validation={"session_status": "RED"},
        portfolio_decision={"overall_status": "FAIL"},
        operational_telemetry={"overall_status": "GREEN"},
        stale_artifacts=["a", "b", "c"],
        recent_errors=["e1", "e2", "e3"],
    )

    assert result["readiness_status"] == "NOT_READY"
    assert result["confidence"] == 0
    assert "runtime_health_not_green" in result["blockers"]
    assert "session_validation_not_green" in result["blockers"]
    assert "recent_errors_exceed_limit" in result["blockers"]


def test_validation_readiness_fails_closed_for_missing_inputs() -> None:
    result = ValidationReadinessEngine().evaluate(
        runtime_health=None,
        session_validation=None,
        portfolio_decision=None,
    )

    assert result["readiness_status"] == "NOT_READY"
    assert "runtime_health_not_green" in result["blockers"]
    assert "session_validation_not_green" in result["blockers"]
    assert "portfolio_decision_not_green" in result["blockers"]
