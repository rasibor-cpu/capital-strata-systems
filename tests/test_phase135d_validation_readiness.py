from __future__ import annotations

from backend.validation.validation_readiness_engine import ValidationReadinessEngine


def test_phase135d_readiness_specific_artifact_warnings_no_false_blocker() -> None:
    result = ValidationReadinessEngine().evaluate(
        runtime_health={"runtime_health": "AMBER"},
        session_validation={"session_status": "GREEN"},
        portfolio_decision={"overall_status": "GREEN", "missing_inputs": []},
        operational_telemetry={"overall_status": "GREEN"},
        runtime_advisory_snapshot={"snapshot_status": "OK", "missing_components": []},
        runtime_portfolio_state={"status": "OK", "portfolio_state": "NO_PORTFOLIO"},
        artifact_freshness={
            "freshness_status": "AMBER",
            "warnings": ["stale_account_state", "no_recent_closed_trades"],
            "blockers": [],
        },
    )

    assert result["readiness_status"] == "READY_WITH_CAUTION"
    assert result["blockers"] == []
    assert "stale_account_state" in result["warnings"]
    assert "no_recent_closed_trades" in result["warnings"]


def test_phase135d_readiness_stale_session_state_blocks() -> None:
    result = ValidationReadinessEngine().evaluate(
        runtime_health={"runtime_health": "RED"},
        session_validation={"session_status": "RED"},
        portfolio_decision={"overall_status": "GREEN", "missing_inputs": []},
        operational_telemetry={"overall_status": "GREEN"},
        runtime_advisory_snapshot={"snapshot_status": "OK", "missing_components": []},
        runtime_portfolio_state={"status": "OK", "portfolio_state": "ACTIVE_PORTFOLIO"},
        artifact_freshness={"freshness_status": "RED", "warnings": ["stale_session_state"], "blockers": ["stale_session_state"]},
    )

    assert result["readiness_status"] == "NOT_READY"
    assert "runtime_health_not_green" in result["blockers"]
    assert "session_validation_not_green" in result["blockers"]
    assert "stale_session_state" in result["warnings"]
