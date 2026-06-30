from __future__ import annotations

from backend.monitoring.runtime_health_aggregator import RuntimeHealthAggregator


def test_phase135e_runtime_health_surfaces_expiring_session() -> None:
    result = RuntimeHealthAggregator().aggregate(
        performance={"overall_status": "GREEN"},
        session_validation={"session_status": "GREEN"},
        supervisor_status={"status": "RUNNING"},
        portfolio_decision={"overall_status": "GREEN"},
        runtime_portfolio_state={"status": "OK", "portfolio_state": "ACTIVE_PORTFOLIO"},
        session_continuity={"session_continuity_status": "EXPIRING_SOON", "warnings": ["session_expiring_soon"]},
    )

    assert result["runtime_health"] == "AMBER"
    assert result["session_continuity_status"] == "EXPIRING_SOON"
    assert "session_expiring_soon" in result["warnings"]


def test_phase135e_runtime_health_expired_session_red_without_crash() -> None:
    result = RuntimeHealthAggregator().aggregate(
        performance={"overall_status": "GREEN"},
        session_validation={"session_status": "GREEN"},
        supervisor_status={"status": "RUNNING"},
        portfolio_decision={"overall_status": "GREEN"},
        runtime_portfolio_state={"status": "OK", "portfolio_state": "ACTIVE_PORTFOLIO"},
        session_continuity={"session_continuity_status": "REAUTH_REQUIRED", "quiet_mode_active": True, "reauth_required": True},
    )

    assert result["runtime_health"] == "RED"
    assert result["quiet_mode_active"] is True
    assert result["reauth_required"] is True
