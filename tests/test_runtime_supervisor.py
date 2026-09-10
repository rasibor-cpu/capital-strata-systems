import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

from dashboard.runtime.runtime_supervisor import (
    MANUAL_INTERVENTION_REQUIRED,
    RuntimeSupervisor,
    SupervisorConfig,
)
from dashboard.runtime.runtime_health_provider import read_runtime_health_snapshot


class FakeProcess:
    _next_pid = 1000

    def __init__(self, *_args, **_kwargs):
        self.pid = FakeProcess._next_pid
        FakeProcess._next_pid += 1
        self.exit_code = None

    def poll(self):
        return self.exit_code

    def terminate(self):
        self.exit_code = 0

    def wait(self, timeout=None):
        return self.exit_code


def test_supervisor_writes_real_child_and_timezone_aware_state(tmp_path: Path):
    supervisor = RuntimeSupervisor(
        SupervisorConfig(state_path=tmp_path / "state.json"),
        process_factory=FakeProcess,
    )
    supervisor.launch_child()
    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))

    assert state["status"] == "HEALTHY"
    assert state["child_pid"] == supervisor.child.pid
    assert "+00:00" in state["started_at_utc"]
    assert "secret" not in json.dumps(state).lower()


def test_supervisor_enforces_bounded_restart_policy(tmp_path: Path):
    supervisor = RuntimeSupervisor(
        SupervisorConfig(state_path=tmp_path / "state.json", poll_seconds=0),
        process_factory=FakeProcess,
    )
    supervisor.launch_child()
    for _ in range(4):
        supervisor.child.exit_code = 1
        if not supervisor.handle_child_exit(1):
            break

    assert supervisor.state["manual_intervention_required"] is True
    assert supervisor.state["status"] == MANUAL_INTERVENTION_REQUIRED
    assert supervisor.state["restart_count"] == 3


def test_shutdown_preserves_fail_closed_authority(tmp_path: Path):
    supervisor = RuntimeSupervisor(
        SupervisorConfig(state_path=tmp_path / "state.json"),
        process_factory=FakeProcess,
    )
    supervisor.launch_child()
    supervisor.shutdown()
    assert supervisor.state["status"] == "STOPPED"


def test_supervisor_refreshes_liveness_while_child_is_active(tmp_path: Path, monkeypatch):
    supervisor = RuntimeSupervisor(
        SupervisorConfig(state_path=tmp_path / "state.json", poll_seconds=0),
        process_factory=FakeProcess,
    )
    supervisor.shutdown = lambda: None

    def stop_after_observation(_seconds):
        supervisor.shutdown_requested = True

    monkeypatch.setattr("dashboard.runtime.runtime_supervisor.time.sleep", stop_after_observation)
    assert supervisor.run() == 0

    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    observed_at = datetime.fromisoformat(state["last_observed_at_utc"])
    assert state["status"] == "HEALTHY"
    assert (datetime.now(timezone.utc) - observed_at).total_seconds() < 5


def test_stale_supervisor_state_is_degraded(tmp_path: Path):
    path = tmp_path / "state.json"
    old = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    path.write_text(json.dumps({"status": "HEALTHY", "last_observed_at_utc": old}), encoding="utf-8")

    snapshot = read_runtime_health_snapshot(
        tmp_path / "runtime.json",
        supervisor_state_path=path,
    )

    assert snapshot["supervisor_status"] == "DEGRADED"