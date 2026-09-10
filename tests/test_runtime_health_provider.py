import json

from dashboard.runtime.runtime_health_provider import read_runtime_health_snapshot


def test_provider_reads_runtime_state_without_mutating_file(tmp_path):
    path = tmp_path / "runtime_supervisor.json"
    source = {
        "start_time": "2026-09-10T00:00:00+00:00",
        "uptime_seconds": 12,
        "cycles_completed": 3,
        "runtime_errors": 0,
        "broker_disconnects": 0,
        "recovery_attempts": 0,
        "alerts_generated": 0,
    }
    path.write_text(json.dumps(source), encoding="utf-8")

    snapshot = read_runtime_health_snapshot(path)

    assert snapshot["process_alive"] is True
    assert snapshot["api_health"] == "HEALTHY"
    assert snapshot["runtime_start_time"] == source["start_time"]
    assert snapshot["cycles_completed"] == 3
    assert json.loads(path.read_text(encoding="utf-8")) == source


def test_provider_missing_state_preserves_unknown_telemetry(tmp_path):
    snapshot = read_runtime_health_snapshot(tmp_path / "missing.json")

    assert snapshot["process_alive"] is True
    assert snapshot["api_health"] == "HEALTHY"
    assert snapshot["state_reason_codes"] == ["RUNTIME_STATE_UNAVAILABLE"]
    assert "heartbeat_status" not in snapshot
    assert snapshot["supervisor_status"] == "UNKNOWN"