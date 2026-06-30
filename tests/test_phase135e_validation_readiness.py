from __future__ import annotations

from backend.validation.validation_readiness_engine import ValidationReadinessEngine


def test_phase135e_readiness_expiring_soon_warns() -> None:
    result = ValidationReadinessEngine().evaluate(
        runtime_health={"runtime_health": "AMBER"},
        session_validation={"session_status": "GREEN"},
        portfolio_decision={"overall_status": "GREEN", "missing_inputs": []},
        operational_telemetry={"overall_status": "GREEN"},
        runtime_advisory_snapshot={"snapshot_status": "OK", "missing_components": []},
        runtime_portfolio_state={"status": "OK", "portfolio_state": "ACTIVE_PORTFOLIO"},
        session_continuity={"session_continuity_status": "EXPIRING_SOON", "warnings": ["session_expiring_soon"]},
    )

    assert result["readiness_status"] == "READY_WITH_CAUTION"
    assert "session_expiring_soon" in result["warnings"]
    assert "session_reauthentication_required" not in result["blockers"]


def test_phase135e_readiness_expired_session_blocks() -> None:
    result = ValidationReadinessEngine().evaluate(
        runtime_health={"runtime_health": "RED"},
        session_validation={"session_status": "GREEN"},
        portfolio_decision={"overall_status": "GREEN", "missing_inputs": []},
        operational_telemetry={"overall_status": "GREEN"},
        runtime_advisory_snapshot={"snapshot_status": "OK", "missing_components": []},
        runtime_portfolio_state={"status": "OK", "portfolio_state": "ACTIVE_PORTFOLIO"},
        session_continuity={"session_continuity_status": "REAUTH_REQUIRED", "reauth_required": True},
    )

    assert result["readiness_status"] == "NOT_READY"
    assert "session_reauthentication_required" in result["blockers"]
