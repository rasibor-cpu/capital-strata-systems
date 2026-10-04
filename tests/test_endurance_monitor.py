"""OV-002 endurance monitor: start refusals, invalidation rules, recorder
restart, terminal-state monotonicity, and one real-process run (supervisor +
uvicorn child + heartbeat publisher) including a SIGKILL of the runtime."""
from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from dashboard.runtime import endurance_monitor as em
from dashboard.runtime.endurance_evidence import HashChainedLedger, read_json

REPO = Path(__file__).resolve().parents[1]
SAFE_POSTURE = {
    "execution_allowed": False, "live_trading_blocked": True, "advisory_only": True,
    "broker_execution_armed": False, "r7_unified_trade_gate_active": True, "data_freshness": "UNAVAILABLE",
}


@pytest.fixture
def git_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    for cmd in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
        subprocess.run(["git", *cmd], cwd=repo, check=True)
    (repo / "config.json").write_text("{}")
    (repo / ".gitignore").write_text("runtime/\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)
    return repo


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ("CSS_TEST_MODE", "CSS_AUTOMATED_INPUT", "CSS_ENV"):
        monkeypatch.delenv(name, raising=False)
    # pytest sets PYTEST_CURRENT_TEST while every test runs, so the real guard
    # would (correctly) refuse; exempt only that name, only here. The guard
    # itself is pinned by test_pytest_marker_is_forbidden_in_a_real_run.
    monkeypatch.setattr(em, "FORBIDDEN_ENV", {k: v for k, v in em.FORBIDDEN_ENV.items() if k != "PYTEST_CURRENT_TEST"})


def test_pytest_marker_is_forbidden_in_a_real_run():
    assert em.forbidden_env_present({"PYTEST_CURRENT_TEST": "x"}) == []  # exempted by the fixture above
    import importlib

    fresh = importlib.reload(importlib.import_module("dashboard.runtime.endurance_monitor"))
    try:
        assert fresh.forbidden_env_present({"PYTEST_CURRENT_TEST": "x"}) == ["PYTEST_CURRENT_TEST"]
        assert fresh.forbidden_env_present({"CSS_ENV": "production"}) == []
    finally:
        importlib.reload(fresh)


def _monitor(git_repo, **kw):
    cfg = em.MonitorConfig(repo=git_repo, evidence_dir=git_repo / "runtime" / "endurance" / "R1", run_id="R1",
                           label="OV-002 ATTEMPT TEST", snapshot_seconds=0.01, **kw)
    return em.EnduranceMonitor(cfg)


def _snap(mon, **over):
    snap = {
        "elapsed_hours": 1.0, "observed_at_utc": "x", "wall_minus_monotonic_drift_seconds": 0.0,
        "wall_clock_step_seconds": 0.0,
        "release": {"head_sha": mon.meta["release"]["head_sha"], "branch": "b", "tracked_tree_clean": True},
        "config_fingerprint": mon.meta["configuration"]["fingerprint"],
        "supervisor": {"alive": True, "unexpected_restart_count": 0, "run_status": "ACTIVE", "terminal_reason": None},
        "runtime": {"heartbeat": {"classification": "HEALTHY"}},
        "safety_posture": dict(SAFE_POSTURE),
    }
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(snap.get(key), dict):
            snap[key] = {**snap[key], **value}
        else:
            snap[key] = value
    return snap


# ---------------------------------------------------------------------------
# Start refusals
# ---------------------------------------------------------------------------
def test_prepare_records_release_identity_and_never_claims_authority(git_repo):
    mon = _monitor(git_repo)
    meta = mon.prepare()
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=git_repo, capture_output=True, text=True).stdout.strip()
    assert meta["release"]["head_sha"] == head
    assert meta["label"] == "OV-002 ATTEMPT TEST"
    assert meta["elapsed_carry_forward_hours"] == 0
    assert meta["certification_authority"] is False
    assert meta["governed_target_hours"] == 72.0
    assert meta["interim_checkpoint_is_certifying"] is False
    assert read_json(mon.status_path)["status"] == em.RUNNING


def test_prepare_refuses_a_dirty_tree(git_repo):
    (git_repo / "config.json").write_text('{"changed": true}')
    with pytest.raises(em.EnduranceRefused, match="not clean"):
        _monitor(git_repo).prepare()


@pytest.mark.parametrize("name,value", [("CSS_TEST_MODE", "1"), ("CSS_AUTOMATED_INPUT", "1"), ("CSS_ENV", "development")])
def test_prepare_refuses_test_or_debug_configuration(git_repo, monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(em.EnduranceRefused, match="forbidden"):
        _monitor(git_repo).prepare()


def test_a_new_attempt_cannot_reuse_an_evidence_directory(git_repo):
    _monitor(git_repo).prepare()
    with pytest.raises(em.EnduranceRefused, match="new run_id"):
        _monitor(git_repo).prepare()


def test_monitor_refuses_a_non_loopback_host(git_repo):
    cfg = em.MonitorConfig(repo=git_repo, evidence_dir=git_repo / "runtime" / "x", run_id="x", label="x", host="0.0.0.0")
    with pytest.raises(em.EnduranceRefused, match="loopback"):
        em.EnduranceMonitor(cfg)


def test_config_fingerprint_never_records_secret_values(git_repo, monkeypatch):
    monkeypatch.setenv("OANDA_API_KEY", "super-secret-value")
    fp = em.config_fingerprint(git_repo)
    assert "super-secret-value" not in json.dumps(fp)
    assert "OANDA_API_KEY" in fp["components"]["env_sha256_by_name"]


# ---------------------------------------------------------------------------
# Invalidation rules
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("over,reason", [
    ({"release": {"head_sha": "f" * 40}}, "RELEASE_SHA_CHANGED"),
    ({"release": {"tracked_tree_clean": False}}, "RELEASE_TREE_MODIFIED"),
    ({"config_fingerprint": "different"}, "CONFIGURATION_SUBSTITUTED"),
    ({"supervisor": {"unexpected_restart_count": 1}}, "UNEXPECTED_ENGINE_RESTART"),
    ({"supervisor": {"run_status": "FAILED", "terminal_reason": "RESTART_LIMIT_EXCEEDED"}},
     "SUPERVISOR_RUN_FAILED:RESTART_LIMIT_EXCEEDED"),
    ({"supervisor": {"alive": False}}, "SUPERVISOR_PROCESS_EXITED"),
    ({"runtime": {"heartbeat": {"classification": "ENGINE_TERMINATED"}}}, "CRITICAL_HEARTBEAT_LOSS:ENGINE_TERMINATED"),
    ({"runtime": {"heartbeat": {"classification": "EVENT_LOOP_BLOCKED"}}}, "CRITICAL_HEARTBEAT_LOSS:EVENT_LOOP_BLOCKED"),
    ({"runtime": {"heartbeat": {"classification": "MONITOR_GAP"}}}, "EVIDENCE_RECORDER_GAP"),
    ({"wall_minus_monotonic_drift_seconds": 900}, "CLOCK_DISCONTINUITY"),
    ({"safety_posture": {"execution_allowed": True}}, "UNAUTHORIZED_EXECUTION_TRANSITION:execution_allowed"),
    ({"safety_posture": {"live_trading_blocked": False}}, "UNAUTHORIZED_EXECUTION_TRANSITION:live_trading_blocked"),
    ({"safety_posture": {"advisory_only": False}}, "UNAUTHORIZED_EXECUTION_TRANSITION:advisory_only"),
    ({"safety_posture": {"broker_execution_armed": True}}, "UNAUTHORIZED_EXECUTION_TRANSITION:broker_execution_armed"),
    ({"safety_posture": {"r7_unified_trade_gate_active": False}}, "R7_TRADE_GATE_INACTIVE"),
])
def test_each_governed_condition_invalidates(git_repo, over, reason):
    mon = _monitor(git_repo)
    mon.prepare()
    mon._posture_ok_mono = time.monotonic()
    assert reason in mon.invalidation_reasons(_snap(mon, **over))


def test_a_clean_snapshot_does_not_invalidate(git_repo):
    mon = _monitor(git_repo)
    mon.prepare()
    mon._posture_ok_mono = time.monotonic()
    assert mon.invalidation_reasons(_snap(mon)) == []


def test_unverifiable_safety_posture_invalidates(git_repo):
    mon = _monitor(git_repo)
    mon.prepare()
    mon._child_launch_mono = time.monotonic() - 1000  # launched long ago, posture never seen
    assert "SAFETY_POSTURE_UNVERIFIABLE" in mon.invalidation_reasons(_snap(mon, safety_posture=None))


def test_invalidation_is_terminal_and_credits_zero_hours(git_repo, monkeypatch):
    mon = _monitor(git_repo)
    mon.prepare()
    monkeypatch.setattr(mon, "observe", lambda: {**_snap(mon, supervisor={"unexpected_restart_count": 1}),
                                                 "child_log_findings": {"tracebacks": 0, "excerpts": []}})
    monkeypatch.setattr(mon, "_heartbeat_diagnostics", lambda _s: None)
    assert mon.tick() == em.INVALIDATED
    invalidation = read_json(mon.dir / "INVALIDATION.json")
    assert invalidation["elapsed_hours_credited"] == 0
    # A later clean observation cannot revert the status.
    mon._set_status(em.RUNNING, reasons=[])
    assert read_json(mon.status_path)["status"] == em.INVALIDATED


def test_interim_checkpoint_is_recorded_but_is_not_completion(git_repo, monkeypatch):
    mon = _monitor(git_repo, interim_checkpoint_hours=23, target_hours=72)
    mon.prepare()
    mon._posture_ok_mono = time.monotonic()
    monkeypatch.setattr(mon, "observe", lambda: {**_snap(mon, elapsed_hours=23.5),
                                                 "child_log_findings": {"tracebacks": 0, "excerpts": []}})
    assert mon.tick() == em.RUNNING
    events = [r["event_type"] for r in HashChainedLedger(mon.dir / "monitor_events.jsonl").verify()]
    assert "INTERIM_CHECKPOINT" in events and "TARGET_REACHED" not in events
    assert (mon.dir / "MANIFEST_INTERIM.json").exists()


# ---------------------------------------------------------------------------
# Recorder restart
# ---------------------------------------------------------------------------
def _seed_snapshot(mon, observed_at):
    mon.snapshots.append("SNAPSHOT", observed_at_utc=observed_at, elapsed_seconds_monotonic=3600.0)


def test_resume_within_threshold_continues_and_carries_elapsed(git_repo):
    mon = _monitor(git_repo)
    mon.prepare()
    _seed_snapshot(mon, datetime.now(timezone.utc).isoformat())
    resumed = em.EnduranceMonitor.resume(mon.c)
    assert resumed.status["status"] == em.RUNNING
    assert resumed._elapsed_before_resume == 3600.0


def test_resume_after_a_long_recorder_gap_invalidates(git_repo):
    mon = _monitor(git_repo)
    mon.prepare()
    _seed_snapshot(mon, (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat())
    resumed = em.EnduranceMonitor.resume(mon.c)
    assert resumed.status["status"] == em.INVALIDATED
    assert resumed.status["reasons"] == ["EVIDENCE_RECORDER_GAP"]


def test_resume_refuses_a_terminal_run(git_repo):
    mon = _monitor(git_repo)
    mon.prepare()
    mon._set_status(em.INVALIDATED, reasons=["X"])
    with pytest.raises(em.EnduranceRefused):
        em.EnduranceMonitor.resume(mon.c)


# ---------------------------------------------------------------------------
# Real processes: supervisor + uvicorn child + heartbeat publisher
# ---------------------------------------------------------------------------
def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait(predicate, timeout=30.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.2)
    return None


@pytest.mark.skipif(os.name == "nt", reason="POSIX signals")
def test_real_runtime_publishes_heartbeat_and_a_killed_child_is_recorded(tmp_path):
    port = _free_port()
    env = {k: v for k, v in os.environ.items() if k not in ("PYTEST_CURRENT_TEST",)}
    env["CSS_RUNTIME_HEARTBEAT_SECONDS"] = "0.2"
    env["PYTHONPATH"] = str(REPO)
    proc = subprocess.Popen(
        [sys.executable, "-m", "dashboard.runtime.runtime_supervisor", "--run-id", "IT-1", "--evidence-dir",
         str(tmp_path), "--port", str(port), "--max-restarts", "0"],
        cwd=REPO, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
    )
    try:
        def beats():
            try:
                hb = read_json(tmp_path / "runtime_heartbeat.json")
            except (OSError, ValueError):
                return None
            return hb if hb.get("thread_seq", 0) >= 3 and hb.get("loop_seq", 0) >= 3 and hb.get("posture") else None

        hb = _wait(beats, timeout=60)
        assert hb, (tmp_path / "child_logs" / "generation_001.log").read_text() if (tmp_path / "child_logs").exists() else "no log"
        assert hb["posture"]["execution_allowed"] is False
        assert hb["posture"]["live_trading_blocked"] is True
        assert hb["posture"]["advisory_only"] is True
        assert hb["posture"]["r7_unified_trade_gate_active"] is True
        child_pid = read_json(tmp_path / "supervisor_state.json")["child_pid"]
        assert hb["pid"] == child_pid

        os.kill(child_pid, signal.SIGKILL)
        assert proc.wait(timeout=30) == 1  # max_restarts=0: the run fails, the supervisor does not continue
        state = read_json(tmp_path / "supervisor_state.json")
        assert state["run_status"] == "FAILED" and state["terminal_reason"] == "RESTART_LIMIT_EXCEEDED"
        assert state["last_exit"]["signal"] == "SIGKILL"
        events = [r["event_type"] for r in HashChainedLedger(tmp_path / "supervisor_events.jsonl").verify()]
        assert events[:2] == ["SUPERVISOR_STARTED", "CHILD_LAUNCHED"]
        assert "CHILD_EXITED_UNEXPECTEDLY" in events and "RUN_FAILED" in events
    finally:
        if proc.poll() is None:
            proc.kill()
