import json
import time
import pytest
from pathlib import Path

from backend.runtime.runtime_supervisor import RuntimeSupervisor
from engine.information.alerts import AlertEventType

class DummyAlertService:
    def __init__(self):
        self.alerts = []

    def dispatch_alert(self, event_type, message, context=None):
        self.alerts.append((event_type, message, context))

@pytest.fixture
def temp_state_file(tmp_path):
    return tmp_path / "runtime_supervisor.json"

@pytest.fixture
def alert_service():
    return DummyAlertService()

def test_supervisor_initializes_with_empty_state_and_creates_start_time(temp_state_file, alert_service):
    supervisor = RuntimeSupervisor(state_file=temp_state_file, alert_service=alert_service)
    
    assert supervisor.state["start_time"] != ""
    assert supervisor.state["uptime_seconds"] == 0
    assert supervisor.state["cycles_completed"] == 0
    assert supervisor.state["alerts_generated"] == 0
    
    # Assert JSON was created
    assert temp_state_file.exists()
    data = json.loads(temp_state_file.read_text())
    assert data["start_time"] == supervisor.state["start_time"]

def test_supervisor_reloads_existing_state(temp_state_file, alert_service):
    # Setup initial state
    supervisor1 = RuntimeSupervisor(state_file=temp_state_file, alert_service=alert_service)
    supervisor1.state["cycles_completed"] = 42
    supervisor1._save_state()
    start_time = supervisor1.state["start_time"]
    
    # Load with new instance
    supervisor2 = RuntimeSupervisor(state_file=temp_state_file, alert_service=alert_service)
    assert supervisor2.state["cycles_completed"] == 42
    assert supervisor2.state["start_time"] == start_time

def test_record_cycle_updates_stats_and_heartbeat(temp_state_file, alert_service):
    supervisor = RuntimeSupervisor(state_file=temp_state_file, alert_service=alert_service)
    
    supervisor.record_cycle(10500.5, "paper", "BALANCED")
    
    assert supervisor.state["cycles_completed"] == 1
    
    hb = supervisor.get_latest_heartbeat()
    assert hb["cycle_number"] == 1
    assert hb["equity"] == 10500.5
    assert hb["broker_mode"] == "paper"
    assert hb["engine_mode"] == "BALANCED"

def test_broker_disconnect_triggers_alert_at_threshold(temp_state_file, alert_service):
    supervisor = RuntimeSupervisor(
        state_file=temp_state_file, 
        broker_disconnect_alert_threshold=3,
        alert_service=alert_service
    )
    
    supervisor.record_broker_disconnect("OANDA", "Timeout 1")
    assert len(alert_service.alerts) == 0
    assert supervisor.state["broker_disconnects"] == 1
    
    supervisor.record_broker_disconnect("OANDA", "Timeout 2")
    assert len(alert_service.alerts) == 0
    
    supervisor.record_broker_disconnect("OANDA", "Timeout 3")
    assert len(alert_service.alerts) == 1
    assert alert_service.alerts[0][0] == AlertEventType.BROKER_CONNECTION_UNSTABLE
    assert supervisor.state["alerts_generated"] == 1

def test_record_recovery_attempt_dispatches_alert(temp_state_file, alert_service):
    supervisor = RuntimeSupervisor(state_file=temp_state_file, alert_service=alert_service)
    
    supervisor.record_recovery_attempt("Network reset")
    
    assert supervisor.state["recovery_attempts"] == 1
    assert len(alert_service.alerts) == 1
    assert alert_service.alerts[0][0] == AlertEventType.RUNTIME_RECOVERY_ATTEMPT
    assert supervisor.state["alerts_generated"] == 1

def test_watchdog_detects_stale_engine(temp_state_file, alert_service):
    supervisor = RuntimeSupervisor(
        state_file=temp_state_file, 
        heartbeat_timeout_seconds=1,  # Fast timeout for test
        alert_service=alert_service
    )
    
    # Pretend heartbeat was long ago
    supervisor.last_heartbeat_time = time.time() - 2.0
    
    supervisor.start_watchdog()
    time.sleep(2.5)  # Let watchdog loop run
    
    assert len(alert_service.alerts) >= 1
    assert alert_service.alerts[0][0] == AlertEventType.ENGINE_HEARTBEAT_LOST
    
    supervisor.stop_watchdog()

def test_record_error_increments_counter(temp_state_file, alert_service):
    supervisor = RuntimeSupervisor(state_file=temp_state_file, alert_service=alert_service)
    
    supervisor.record_error("Test exception")
    
    assert supervisor.state["runtime_errors"] == 1

def test_fail_safe_behavior_on_corrupt_file(tmp_path, alert_service):
    # Create unparseable file
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{bad json}")
    
    # Should not crash
    supervisor = RuntimeSupervisor(state_file=bad_file, alert_service=alert_service)
    assert supervisor.state["start_time"] != ""  # Auto-initialized new state
    
    # Saving should overwrite with valid JSON
    supervisor.record_cycle(100.0, "paper", "SAFE")
    data = json.loads(bad_file.read_text())
    assert data["cycles_completed"] == 1
