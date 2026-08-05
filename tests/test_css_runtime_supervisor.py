import os
import json
import tempfile
import pytest
from unittest.mock import MagicMock

from backend.monitoring.css_alert_models import AlertSeverity
from backend.runtime.css_runtime_supervisor import CSSRuntimeSupervisor

@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as td:
        yield td

@pytest.fixture
def supervisor(temp_dir):
    alert_mock = MagicMock()
    return CSSRuntimeSupervisor(state_dir=temp_dir, trusted_root=temp_dir, max_restart_limit=2, alert_service=alert_mock)

def test_supervisor_start(supervisor):
    assert supervisor.status == "STOPPED"
    supervisor.start()
    assert supervisor.status == "RUNNING"
    assert supervisor.started_at is not None
    assert supervisor.stopped_at is None
    supervisor.alert_service.emit_system_alert.assert_called_once()

def test_supervisor_stop(supervisor):
    supervisor.start()
    supervisor.stop()
    assert supervisor.status == "STOPPED"
    assert supervisor.stopped_at is not None

def test_supervisor_heartbeat(supervisor):
    supervisor.start()
    assert supervisor.last_heartbeat_at is None
    supervisor.heartbeat()
    assert supervisor.last_heartbeat_at is not None

def test_supervisor_failure_recording_and_restart_decision(supervisor):
    supervisor.start()

    supervisor.record_failure("Test error 1")
    assert supervisor.failure_count == 1
    assert supervisor.status == "DEGRADED"
    assert supervisor.should_restart() is True

    supervisor.record_restart_attempt("CSS Runtime", attempt=1, delay_seconds=0.0)
    assert supervisor.should_restart() is True

    supervisor.record_restart_attempt("CSS Runtime", attempt=2, delay_seconds=0.0)
    assert supervisor.status == "FAILED"
    assert supervisor.should_restart() is False

def test_supervisor_record_restart(supervisor):
    supervisor.start()
    supervisor.record_failure("Oops")
    assert supervisor.status == "DEGRADED"
    
    supervisor.record_restart()
    assert supervisor.restart_count == 1
    assert supervisor.status == "RUNNING"
    assert supervisor.started_at is not None

def test_state_persistence(supervisor, temp_dir):
    supervisor.start()
    supervisor.record_failure("Database timeout")
    
    state_file = os.path.join(temp_dir, "css_runtime_supervisor_state.json")
    assert os.path.exists(state_file)
    
    with open(state_file, "r") as f:
        state = json.load(f)
        
    assert state["status"] == "DEGRADED"
    assert state["failure_count"] == 1
    assert state["last_failure"] == "Database timeout"

def test_alert_failure_does_not_crash_supervisor(temp_dir):
    alert_mock = MagicMock()
    alert_mock.emit_system_alert.side_effect = Exception("Alert system down")
    
    # This should not raise an exception
    sup = CSSRuntimeSupervisor(state_dir=temp_dir, trusted_root=temp_dir, alert_service=alert_mock)
    sup.start()
    sup.record_failure("Some error")
    
    assert sup.status == "DEGRADED"

def test_get_status(supervisor):
    supervisor.start()
    supervisor.record_failure("Network drop")
    status = supervisor.get_status()
    
    assert "supervisor_id" in status
    assert status["status"] == "DEGRADED"
    assert status["failure_count"] == 1
    assert status["last_failure"] == "Network drop"
    assert status["max_restart_limit"] == 2


def test_cumulative_successful_restart_limit_below_at_and_above(temp_dir):
    alert_mock = MagicMock()
    sup = CSSRuntimeSupervisor(state_dir=temp_dir, trusted_root=temp_dir, max_restart_limit=2, alert_service=alert_mock)
    sup.start()

    sup.record_failure("first", service_name="CSS Runtime", pid_before=100)
    assert sup.should_restart() is True
    sup.record_restart_success("CSS Runtime", attempt=1, pid_before=100, pid_after=101)
    assert sup.restart_count == 1
    assert sup.process_generation == 1

    sup.record_failure("second", service_name="CSS Runtime", pid_before=101)
    assert sup.should_restart() is True
    sup.record_restart_success("CSS Runtime", attempt=2, pid_before=101, pid_after=102)
    assert sup.restart_count == 2
    assert sup.restart_limit_exhausted is True

    sup.record_failure("third", service_name="CSS Runtime", pid_before=102)
    assert sup.should_restart() is False
    sup.record_restart_success("CSS Runtime", attempt=3, pid_before=102, pid_after=103)
    assert sup.restart_count == 2
    assert sup.status == "FAILED"
    assert sup.restart_limit_exhausted is True


def test_durable_bounded_failure_history(temp_dir):
    alert_mock = MagicMock()
    sup = CSSRuntimeSupervisor(
        state_dir=temp_dir,
        trusted_root=temp_dir,
        max_restart_limit=5,
        alert_service=alert_mock,
        failure_history_limit=3,
    )
    sup.start()

    for idx in range(5):
        sup.record_failure(f"failure {idx}", service_name="CSS Runtime", pid_before=idx)

    status = sup.get_status()
    assert len(status["failure_history"]) == 3
    assert status["failure_history"][0]["reason"] == "failure 2"

    history_path = temp_dir + os.sep + "css_runtime_supervisor_failure_history.jsonl"
    with open(history_path, "r", encoding="utf-8") as handle:
        lines = handle.readlines()
    assert len(lines) == 5
    assert all("process_generation" in json.loads(line) for line in lines)


def test_process_tree_identity_tracks_generation_and_pids(temp_dir):
    alert_mock = MagicMock()
    sup = CSSRuntimeSupervisor(state_dir=temp_dir, trusted_root=temp_dir, max_restart_limit=3, alert_service=alert_mock)
    sup.start()
    sup.record_process_tree(
        launcher_pid=10,
        supervisor_pid=10,
        managed_services={"CSS Runtime": {"pid": 20}, "Mobile Launcher": {"pid": 30}},
    )

    sup.record_failure("runtime exit", service_name="CSS Runtime", pid_before=20)
    sup.record_restart_success("CSS Runtime", attempt=1, pid_before=20, pid_after=21)

    status = sup.get_status()
    assert status["process_generation"] == 1
    assert status["process_identity"]["launcher_pid"] == 10
    assert status["process_identity"]["managed_services"]["CSS Runtime"]["pid"] == 21
    assert status["failure_history"][-1]["pid_before"] == 20
    assert status["failure_history"][-1]["pid_after"] == 21


def test_controlled_shutdown_history_is_explicit_not_unexpected(temp_dir):
    alert_mock = MagicMock()
    sup = CSSRuntimeSupervisor(state_dir=temp_dir, trusted_root=temp_dir, max_restart_limit=1, alert_service=alert_mock)
    sup.start()
    sup.stop()

    status = sup.get_status()
    assert status["status"] == "STOPPED"
    assert status["shutdown_requested"] is True
    assert status["failure_history"][-1]["event_type"] == "controlled_shutdown"
