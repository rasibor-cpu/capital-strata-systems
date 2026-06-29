from __future__ import annotations

import datetime as dt

from backend.monitoring.session_validation_engine import SessionValidationEngine


NOW = dt.datetime(2026, 6, 29, 12, 0, tzinfo=dt.UTC)


def test_session_validation_healthy_runtime() -> None:
    result = SessionValidationEngine().validate(
        session_state={"session": {"start_time": "2026-06-29T11:00:00Z"}},
        supervisor_state={"status": "RUNNING", "last_heartbeat": "2026-06-29T11:59:30Z", "restart_count": 0},
        artifact_status={"account.json": {"age_seconds": 10, "stale_after_seconds": 300}},
        advisory_status={"recommendations": ["MAINTAIN", "MAINTAIN"], "policy_consistency": True, "persistence_health": "OK"},
        now=NOW,
    )

    assert result["status"] == "OK"
    assert result["session_status"] == "GREEN"
    assert result["session_duration"] == 3600
    assert result["heartbeat_age"] == 30
    assert result["recommendation_stability"] == "STABLE"
    assert result["stale_artifacts"] == []


def test_session_validation_degraded_stale_artifacts() -> None:
    result = SessionValidationEngine().validate(
        session_state={"session": {"start_time": "2026-06-29T11:00:00Z"}},
        supervisor_state={"status": "RUNNING", "last_heartbeat": "2026-06-29T11:58:30Z", "restart_count": 1, "recovery_count": 1},
        artifact_status={"account.json": {"age_seconds": 500, "stale_after_seconds": 300}},
        advisory_status={"recommendations": ["MAINTAIN", "REDUCE_RISK"], "policy_consistency": True, "persistence_health": "OK"},
        now=NOW,
    )

    assert result["session_status"] == "AMBER"
    assert result["restart_count"] == 1
    assert result["recovery_count"] == 1
    assert result["stale_artifacts"] == ["account.json"]
    assert result["recommendation_stability"] == "CHANGING"


def test_session_validation_stale_heartbeat_and_fail_closed() -> None:
    stale = SessionValidationEngine().validate(
        session_state={"session": {"start_time": "2026-06-29T11:00:00Z"}},
        supervisor_state={"status": "RUNNING", "last_heartbeat": "2026-06-29T11:00:00Z"},
        artifact_status={},
        advisory_status={"policy_consistency": True, "persistence_health": "OK"},
        now=NOW,
    )
    unavailable = SessionValidationEngine().validate(None)

    assert stale["session_status"] == "RED"
    assert stale["heartbeat_age"] == 3600
    assert unavailable["status"] == "DATA UNAVAILABLE"
    assert unavailable["session_status"] == "RED"
