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
    return CSSRuntimeSupervisor(state_dir=temp_dir, max_restart_limit=2, alert_service=alert_mock)

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
    
    # 1st failure
    supervisor.record_failure("Test error 1")
    assert supervisor.failure_count == 1
    assert supervisor.status == "DEGRADED"
    assert supervisor.should_restart() is True

    # 2nd failure
    supervisor.record_failure("Test error 2")
    assert supervisor.failure_count == 2
    assert supervisor.status == "DEGRADED"
    assert supervisor.should_restart() is True

    # 3rd failure (limit exceeded since max is 2)
    supervisor.record_failure("Test error 3")
    assert supervisor.failure_count == 3
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
    sup = CSSRuntimeSupervisor(state_dir=temp_dir, alert_service=alert_mock)
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
