from datetime import datetime, timedelta, timezone

from dashboard.runtime.api_bridge import create_app
from dashboard.runtime.dashboard_state import DashboardState
from dashboard.runtime.runtime_operational_state import (
    HEALTHY,
    LOST,
    MANUAL_INTERVENTION_REQUIRED,
    STALE,
    build_runtime_operational_state,
    evaluate_restart_policy,
)


def _healthy_snapshot(now: datetime) -> dict[str, object]:
    return {
        "process_alive": True,
        "heartbeat_at": now.isoformat(),
        "api_health": "HEALTHY",
        "supervisor_status": "HEALTHY",
        "broker_data_freshness": "CURRENT",
    }


def test_healthy_runtime_is_unattended_ready_but_not_execution_ready():
    now = datetime.now(timezone.utc)
    state = build_runtime_operational_state(_healthy_snapshot(now), now=now)

    assert state.runtime_status == "RUNNING"
    assert state.heartbeat_status == HEALTHY
    assert state.unattended_ready is True
    assert state.advisory_only is True
    assert state.execution_allowed is False
    assert state.live_trading_blocked is True
    assert state.broker_execution_armed is False


def test_stale_and_lost_heartbeat_fail_closed():
    now = datetime.now(timezone.utc)
    stale = build_runtime_operational_state(
        _healthy_snapshot(now - timedelta(seconds=90)), now=now
    )
    lost = build_runtime_operational_state(
        _healthy_snapshot(now - timedelta(seconds=240)), now=now
    )

    assert stale.heartbeat_status == STALE
    assert stale.unattended_ready is False
    assert lost.heartbeat_status == LOST
    assert lost.runtime_status == "DEGRADED"
    assert any(alert.code == "ENGINE_HEARTBEAT_LOST" for alert in lost.alerts)


def test_stale_broker_and_critical_alert_block_unattended_operation():
    now = datetime.now(timezone.utc)
    state = build_runtime_operational_state(
        {**_healthy_snapshot(now), "broker_data_freshness": "STALE"}, now=now
    )

    assert state.unattended_ready is False
    assert any(alert.code == "BROKER_DATA_STALE" for alert in state.alerts)
    assert all(alert.safety_state["execution_allowed"] is False for alert in state.alerts)
    assert all("next_action" not in alert.as_dict() or alert.next_action for alert in state.alerts)


def test_restart_policy_is_bounded_and_enters_manual_intervention():
    now = datetime.now(timezone.utc)
    recent = [(now - timedelta(seconds=seconds)).isoformat() for seconds in (1, 2, 3)]
    decision = evaluate_restart_policy(recent, now=now, max_restarts=3, window_seconds=300)

    assert decision.allowed is False
    assert decision.recovery_status == MANUAL_INTERVENTION_REQUIRED
    assert decision.restart_count == 3


def test_recovery_failure_and_process_exit_are_alerted_without_authority():
    now = datetime.now(timezone.utc)
    state = build_runtime_operational_state(
        {
            "process_alive": False,
            "heartbeat_status": "LOST",
            "api_health": "FAILED",
            "supervisor_status": "FAILED",
            "broker_data_freshness": "STALE",
            "recovery_status": "RECOVERY_FAILED",
        },
        now=now,
    )

    codes = {alert.code for alert in state.alerts}
    assert {"UNEXPECTED_PROCESS_EXIT", "SUPERVISOR_FAILURE", "RECOVERY_FAILED"} <= codes
    assert state.execution_allowed is False
    assert state.live_trading_blocked is True


def test_runtime_routes_are_read_only_and_mission_control_exposes_runtime():
    app = create_app(lambda: DashboardState())
    paths = set(app.openapi()["paths"])

    assert "/api/v1/runtime-health" in paths
    assert "/api/v1/runtime-alerts" in paths
    assert "/api/v1/mission-control" in paths
    assert not any(path.startswith("/api/v1/runtime/") and path not in {"/api/v1/runtime-health", "/api/v1/runtime-alerts"} for path in paths)
