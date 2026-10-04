"""Regression tests for the OV-002 Attempt-2 failure modes on this release line.

* restart limit: cumulative per run, persistent, terminal, not resettable;
* exit causes (code / signal), PID transitions and child output retained;
* heartbeat loss classified, never confused with shutdown, startup or a
  monitor stall; thresholds are the governed ones;
* evidence ledgers are tamper-evident and survive restart.
"""
from __future__ import annotations

import json
import signal
import subprocess

import pytest

from dashboard.runtime import heartbeat_diagnostics as hd
from dashboard.runtime.endurance_evidence import (
    HashChainedLedger,
    LedgerError,
    atomic_write_json,
    build_manifest,
    verify_manifest,
)
from dashboard.runtime.runtime_operational_state import _HEARTBEAT_LOST_SECONDS, _HEARTBEAT_STALE_SECONDS
from dashboard.runtime.runtime_supervisor import (
    MANUAL_INTERVENTION_REQUIRED,
    RUN_FAILED,
    RUN_STOPPED,
    RuntimeSupervisor,
    SupervisorConfig,
    SupervisorRunRefused,
    describe_exit_code,
)


class FakeProcess:
    _next_pid = 5000
    launched: list[dict] = []

    def __init__(self, command, **kwargs):
        self.pid = FakeProcess._next_pid
        FakeProcess._next_pid += 1
        self.exit_code = None
        FakeProcess.launched.append({"command": command, **kwargs})

    def poll(self):
        return self.exit_code

    def terminate(self):
        self.exit_code = -15

    def wait(self, timeout=None):
        return self.exit_code

    def kill(self):
        self.exit_code = -9


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr("dashboard.runtime.runtime_supervisor.time.sleep", lambda _s: None)
    FakeProcess.launched.clear()


def _supervisor(tmp_path, *, run_id="RUN-T", window=0, max_restarts=3, evidence=True):
    return RuntimeSupervisor(
        SupervisorConfig(
            state_path=tmp_path / "supervisor_state.json",
            run_id=run_id,
            evidence_dir=tmp_path if evidence else None,
            max_restarts=max_restarts,
            restart_window_seconds=window,
        ),
        process_factory=FakeProcess,
    )


def _ledger(tmp_path):
    return HashChainedLedger(tmp_path / "supervisor_events.jsonl").verify()


# ---------------------------------------------------------------------------
# Restart limit (Attempt 2: restart_count=8 against max_restart_limit=3)
# ---------------------------------------------------------------------------
def test_limit_is_cumulative_for_the_run_even_when_restarts_are_spread_out(tmp_path):
    # window=0: the rolling window never trips, exactly the spread-out crash
    # pattern the old consecutive-failure check let through indefinitely.
    sup = _supervisor(tmp_path, window=0)
    sup.launch_child()
    outcomes = [sup.handle_child_exit(1) for _ in range(4)]
    assert outcomes == [True, True, True, False]
    assert sup.state["run_status"] == RUN_FAILED
    assert sup.state["terminal_reason"] == "RESTART_LIMIT_EXCEEDED"
    assert sup.state["status"] == MANUAL_INTERVENTION_REQUIRED
    assert sup.state["restart_count"] == 3
    assert sup.state["unexpected_restart_count"] == 4
    assert len(FakeProcess.launched) == 4  # initial + 3 restarts, never a 5th
    assert _ledger(tmp_path)[-1]["event_type"] == "RUN_FAILED"


def test_successful_restarts_never_reset_the_counter(tmp_path):
    sup = _supervisor(tmp_path, window=0, max_restarts=10)
    sup.launch_child()
    counts = []
    for _ in range(5):
        sup.handle_child_exit(1)
        counts.append(sup.state["unexpected_restart_count"])
    assert counts == [1, 2, 3, 4, 5]


def test_counter_survives_a_supervisor_restart(tmp_path):
    first = _supervisor(tmp_path)
    first.launch_child()
    first.handle_child_exit(1)
    first.handle_child_exit(1)
    second = _supervisor(tmp_path)  # same run_id: e.g. the supervisor process was restarted
    assert second.state["unexpected_restart_count"] == 2
    second.launch_child()
    assert second.handle_child_exit(1) is True
    assert second.handle_child_exit(1) is False  # 4th unexpected exit across both processes
    assert second.state["run_status"] == RUN_FAILED


def test_a_failed_run_cannot_be_relaunched_or_resumed(tmp_path):
    sup = _supervisor(tmp_path, max_restarts=0)
    sup.launch_child()
    assert sup.handle_child_exit(1) is False
    with pytest.raises(SupervisorRunRefused):
        sup.launch_child()
    with pytest.raises(SupervisorRunRefused):
        _supervisor(tmp_path, max_restarts=0)


def test_hand_editing_the_state_file_cannot_revive_or_launder_a_run(tmp_path):
    sup = _supervisor(tmp_path, max_restarts=1)
    sup.launch_child()
    sup.handle_child_exit(1)
    sup.handle_child_exit(1)
    state_path = tmp_path / "supervisor_state.json"
    edited = json.loads(state_path.read_text())
    edited.update(run_status="ACTIVE", terminal_reason=None, unexpected_restart_count=0, restart_count=0)
    state_path.write_text(json.dumps(edited))
    with pytest.raises(SupervisorRunRefused) as exc:
        _supervisor(tmp_path, max_restarts=1)
    assert exc.value.code == "RUN_ALREADY_TERMINAL_IN_LEDGER"


def test_lowered_counter_in_state_file_is_restored_from_the_ledger(tmp_path):
    sup = _supervisor(tmp_path)
    sup.launch_child()
    sup.handle_child_exit(1)
    sup.handle_child_exit(1)
    state_path = tmp_path / "supervisor_state.json"
    edited = json.loads(state_path.read_text())
    edited.update(unexpected_restart_count=0, restart_count=0)
    state_path.write_text(json.dumps(edited))
    resumed = _supervisor(tmp_path)
    assert resumed.state["unexpected_restart_count"] == 2
    assert resumed.state["restart_count"] == 2


def test_deleting_the_state_file_does_not_start_the_run_over(tmp_path):
    sup = _supervisor(tmp_path)
    sup.launch_child()
    sup.handle_child_exit(1)
    (tmp_path / "supervisor_state.json").unlink()
    with pytest.raises(SupervisorRunRefused) as exc:
        _supervisor(tmp_path)
    assert exc.value.code == "SUPERVISOR_STATE_MISSING_FOR_EXISTING_RUN"


def test_controlled_shutdown_is_terminal_and_records_the_signal(tmp_path):
    sup = _supervisor(tmp_path)
    sup.launch_child()
    sup.request_shutdown(signal.SIGTERM)
    sup.shutdown()
    assert sup.state["run_status"] == RUN_STOPPED
    assert sup.state["terminal_reason"] == "CONTROLLED_SHUTDOWN:SIGTERM"
    stopped = _ledger(tmp_path)[-1]
    assert stopped["event_type"] == "SUPERVISOR_STOPPED" and stopped["signal"] == "SIGTERM"
    with pytest.raises(SupervisorRunRefused):
        _supervisor(tmp_path)


def test_legacy_config_without_run_id_keeps_existing_behaviour(tmp_path):
    sup = _supervisor(tmp_path, run_id=None, evidence=False, window=300)
    sup.launch_child()
    for _ in range(4):
        if not sup.handle_child_exit(1):
            break
    assert sup.state["restart_count"] == 3
    assert sup.state["manual_intervention_required"] is True


# ---------------------------------------------------------------------------
# Exit cause, PID transitions, child output (all lost in Attempt 2)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("code,expected", [
    (-15, ("SIGTERM", "terminated by SIGTERM")),
    (-9, ("SIGKILL", "terminated by SIGKILL")),
    (1, (None, "error exit")),
    (0, (None, "clean exit")),
    (0xC000013A, (None, "NTSTATUS 0xC000013A")),
])
def test_exit_codes_are_decoded(code, expected):
    info = describe_exit_code(code)
    assert (info["signal"], info["description"]) == expected


def test_exit_code_pid_transition_and_child_log_hash_are_recorded(tmp_path):
    sup = _supervisor(tmp_path)
    sup.launch_child()
    first_pid = sup.child.pid
    (tmp_path / "child_logs" / "generation_001.log").open("a").write("Traceback (most recent call last):\n")
    sup.handle_child_exit(-9)
    rows = _ledger(tmp_path)
    exited = next(r for r in rows if r["event_type"] == "CHILD_EXITED_UNEXPECTEDLY")
    assert exited["signal"] == "SIGKILL" and exited["child_pid"] == first_pid
    assert exited["child_log_sha256"] and len(exited["child_log_sha256"]) == 64
    relaunch = [r for r in rows if r["event_type"] == "CHILD_LAUNCHED"][-1]
    assert relaunch["previous_child_pid"] is None or relaunch["previous_child_pid"] == first_pid
    assert relaunch["child_pid"] != first_pid
    assert sup.state["last_exit"]["signal"] == "SIGKILL"


def test_child_is_headless_and_told_where_to_publish_its_heartbeat(tmp_path):
    sup = _supervisor(tmp_path)
    sup.launch_child()
    launched = FakeProcess.launched[-1]
    assert launched["stdin"] is subprocess.DEVNULL  # an input() prompt fails fast, never blocks
    assert launched["stderr"] is subprocess.STDOUT
    assert launched["env"]["CSS_RUNTIME_HEARTBEAT_FILE"] == str(tmp_path / "runtime_heartbeat.json")


# ---------------------------------------------------------------------------
# Heartbeat classification
# ---------------------------------------------------------------------------
def _obs(**kw):
    base = dict(monitor_gap_seconds=60, seconds_since_launch=3600, thread_gap_seconds=5, loop_gap_seconds=5,
                pid=123, pid_alive=True, shutdown_requested=False, wall_minus_monotonic_drift_seconds=0.0)
    base.update(kw)
    return hd.classify_heartbeat(hd.HeartbeatObservation(**base))


def test_thresholds_are_the_governed_values_not_redefined():
    assert hd.STALE_SECONDS == _HEARTBEAT_STALE_SECONDS == 60
    assert hd.LOST_SECONDS == _HEARTBEAT_LOST_SECONDS == 180
    assert hd.STARTUP_GRACE_SECONDS < hd.LOST_SECONDS


@pytest.mark.parametrize("kw,expected,critical", [
    ({}, hd.HEALTHY, False),
    ({"thread_gap_seconds": 90, "loop_gap_seconds": 90}, hd.STALE, False),
    ({"pid_alive": False}, hd.ENGINE_TERMINATED, True),
    ({"thread_gap_seconds": 400}, hd.PROCESS_HUNG, True),
    ({"loop_gap_seconds": 400}, hd.EVENT_LOOP_BLOCKED, True),
    ({"monitor_gap_seconds": 400, "thread_gap_seconds": 400}, hd.MONITOR_GAP, False),
    ({"shutdown_requested": True, "pid_alive": False}, hd.CONTROLLED_SHUTDOWN, False),
    ({"thread_gap_seconds": None, "loop_gap_seconds": None, "seconds_since_launch": 30}, hd.STARTUP_GRACE, False),
    ({"thread_gap_seconds": None, "loop_gap_seconds": None, "seconds_since_launch": 400}, hd.NO_HEARTBEAT_SOURCE, True),
    ({"wall_minus_monotonic_drift_seconds": 3600}, hd.CLOCK_ANOMALY, False),
])
def test_heartbeat_loss_is_classified(kw, expected, critical):
    result = _obs(**kw)
    assert result.classification == expected
    assert result.critical is critical


def test_a_clock_step_never_masks_a_real_runtime_loss():
    assert _obs(pid_alive=False, wall_minus_monotonic_drift_seconds=3600).classification == hd.ENGINE_TERMINATED
    assert _obs(loop_gap_seconds=400, wall_minus_monotonic_drift_seconds=-3600).classification == hd.EVENT_LOOP_BLOCKED


def test_startup_grace_is_bounded():
    # Attempt 2's heartbeat losses fired exactly 600 s after a restart with no
    # first beat. With the grace bounded below LOST, a runtime that never
    # beats is lost by 180 s, not hidden for 10 minutes.
    assert _obs(thread_gap_seconds=None, loop_gap_seconds=None, seconds_since_launch=181).critical is True


# ---------------------------------------------------------------------------
# Evidence integrity
# ---------------------------------------------------------------------------
def test_ledger_detects_edit_deletion_and_continues_after_reopen(tmp_path):
    path = tmp_path / "l.jsonl"
    ledger = HashChainedLedger(path)
    ledger.append("A", n=1)
    ledger.append("B", n=2)
    reopened = HashChainedLedger(path)  # recorder restart
    reopened.append("C", n=3)
    assert [r["seq"] for r in reopened.verify()] == [1, 2, 3]

    lines = path.read_text().splitlines()
    path.write_text("\n".join([lines[0], lines[2]]) + "\n")  # delete a row
    with pytest.raises(LedgerError):
        HashChainedLedger(path).verify()
    path.write_text("\n".join([lines[0], lines[1].replace('"n":2', '"n":9'), lines[2]]) + "\n")  # edit a row
    with pytest.raises(LedgerError):
        HashChainedLedger(path).verify()


def test_manifest_detects_changed_and_missing_files_but_allows_appends(tmp_path):
    (tmp_path / "a.jsonl").write_text("row1\n")
    atomic_write_json(tmp_path / "b.json", {"x": 1})
    manifest = build_manifest(tmp_path)
    with open(tmp_path / "a.jsonl", "a") as handle:
        handle.write("row2\n")  # append-only growth is fine
    assert verify_manifest(tmp_path, manifest) == []
    (tmp_path / "a.jsonl").write_text("ROW1\nrow2\n")
    (tmp_path / "b.json").unlink()
    assert sorted(verify_manifest(tmp_path, manifest)) == ["changed: a.jsonl", "missing: b.json"]
