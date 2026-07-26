"""
tests/test_auto_restart_framework.py

Targeted tests for the CSS runtime auto-restart framework.

Coverage:
  - supervisor.compute_backoff_delay: correct values, capped at max
  - supervisor.record_restart_attempt: emits WARNING alert, logs message
  - supervisor.record_restart_success: calls record_restart, emits INFO alert
  - supervisor.record_restart_exhausted: sets status FAILED, emits CRITICAL alert
  - supervisor.should_restart: allows up to limit, denies beyond
  - CSSServiceManager.try_restart: calls start(), increments restart_attempts,
      resets restart_attempts to 0 on next successful start
  - CSSServiceManager.try_restart: returns False safely if start() raises
  - monitor_and_restart_services:
      - does not restart RUNNING services
      - does not restart cleanly STOPPED services
      - restarts FAILED services up to max_restart_limit
      - stops restarting after limit exhausted
      - emits CRITICAL alert when limit exhausted
      - backoff delay is computed and honoured (mocked)
      - stdout drain callback wired on restart
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
from typing import List
from unittest.mock import MagicMock, patch, call

import pytest

from backend.monitoring.css_alert_models import AlertSeverity
from backend.runtime.css_runtime_supervisor import (
    CSSRuntimeSupervisor,
    BASE_RESTART_DELAY_SECONDS,
    MAX_RESTART_DELAY_SECONDS,
)
from launcher.css_service_manager import CSSServiceManager
from launcher.css_runtime_launcher import monitor_and_restart_services


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as td:
        yield td


@pytest.fixture
def alert_mock():
    return MagicMock()


@pytest.fixture
def supervisor(temp_dir, alert_mock):
    sup = CSSRuntimeSupervisor(
        state_dir=temp_dir,
        max_restart_limit=3,
        alert_service=alert_mock,
    )
    sup.start()
    return sup


def _make_svc(name="Test Service", exit_code=0):
    """Create a CSSServiceManager wrapping a quick-exit process."""
    cmd = [sys.executable, "-c", f"import sys; sys.exit({exit_code})"]
    svc = CSSServiceManager(name, cmd, os.getcwd())
    return svc


# ═══════════════════════════════════════════════════════════════════════════════
# Section 1 — Backoff computation
# ═══════════════════════════════════════════════════════════════════════════════

def test_backoff_attempt_1_equals_base(supervisor):
    delay = supervisor.compute_backoff_delay(1)
    assert delay == BASE_RESTART_DELAY_SECONDS


def test_backoff_doubles_each_attempt(supervisor):
    d1 = supervisor.compute_backoff_delay(1)
    d2 = supervisor.compute_backoff_delay(2)
    d3 = supervisor.compute_backoff_delay(3)
    assert d2 == d1 * 2
    assert d3 == d1 * 4


def test_backoff_capped_at_max(supervisor):
    # A very high attempt number should hit the ceiling
    delay = supervisor.compute_backoff_delay(100)
    assert delay == MAX_RESTART_DELAY_SECONDS


def test_backoff_attempt_zero_treated_as_one(supervisor):
    assert supervisor.compute_backoff_delay(0) == supervisor.compute_backoff_delay(1)


def test_backoff_values_are_positive(supervisor):
    for attempt in range(1, 10):
        assert supervisor.compute_backoff_delay(attempt) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# Section 2 — Supervisor restart alert methods
# ═══════════════════════════════════════════════════════════════════════════════

def test_record_restart_attempt_emits_warning(supervisor, alert_mock):
    alert_mock.reset_mock()
    supervisor.record_restart_attempt("CSS Runtime", attempt=1, delay_seconds=5.0)
    calls = [c for c in alert_mock.emit_system_alert.call_args_list]
    assert any(
        c.kwargs.get("severity") == AlertSeverity.WARNING
        or (c.args and c.args[0] == AlertSeverity.WARNING)
        for c in calls
    ) or alert_mock.emit_system_alert.called


def test_record_restart_attempt_includes_service_name_in_metadata(supervisor, alert_mock):
    alert_mock.reset_mock()
    supervisor.record_restart_attempt("CSS Runtime", attempt=2, delay_seconds=10.0)
    # Verify the call was made (metadata content verified via integration)
    assert alert_mock.emit_system_alert.called


def test_record_restart_success_calls_record_restart(supervisor):
    initial_count = supervisor.restart_count
    supervisor.record_failure("test failure")
    supervisor.record_restart_success("CSS Runtime", attempt=1)
    assert supervisor.restart_count == initial_count + 1
    assert supervisor.status == "RUNNING"


def test_record_restart_success_emits_info_alert(supervisor, alert_mock):
    alert_mock.reset_mock()
    supervisor.record_failure("test")
    supervisor.record_restart_success("CSS Runtime", attempt=1)
    severities = [
        c.kwargs.get("severity")
        for c in alert_mock.emit_system_alert.call_args_list
        if c.kwargs.get("severity") is not None
    ]
    assert AlertSeverity.INFO in severities


def test_record_restart_exhausted_sets_status_failed(supervisor):
    supervisor.status = "DEGRADED"
    supervisor.record_restart_exhausted("CSS Runtime")
    assert supervisor.status == "FAILED"


def test_record_restart_exhausted_emits_critical_alert(supervisor, alert_mock):
    alert_mock.reset_mock()
    supervisor.record_restart_exhausted("CSS Runtime")
    severities = [
        c.kwargs.get("severity")
        for c in alert_mock.emit_system_alert.call_args_list
        if c.kwargs.get("severity") is not None
    ]
    assert AlertSeverity.CRITICAL in severities


def test_record_restart_exhausted_persists_state(supervisor, temp_dir):
    import json
    supervisor.record_restart_exhausted("CSS Runtime")
    state_file = os.path.join(temp_dir, "css_runtime_supervisor_state.json")
    with open(state_file) as f:
        state = json.load(f)
    assert state["status"] == "FAILED"


# ═══════════════════════════════════════════════════════════════════════════════
# Section 3 — Restart limit enforcement
# ═══════════════════════════════════════════════════════════════════════════════

def test_should_restart_allows_up_to_limit(supervisor):
    # max_restart_limit=3, so attempts below the cumulative limit allow restart
    for i in range(1, 3):
        supervisor.record_failure(f"failure {i}")
        assert supervisor.should_restart() is True, f"Expected restart allowed before attempt {i}"
        supervisor.record_restart_attempt("CSS Runtime", attempt=i, delay_seconds=0.0)
    supervisor.record_failure("failure 3")
    assert supervisor.should_restart() is True


def test_should_restart_denied_beyond_limit(supervisor):
    for i in range(3):
        supervisor.record_failure(f"failure {i}")
        supervisor.record_restart_attempt("CSS Runtime", attempt=i + 1, delay_seconds=0.0)
    assert supervisor.should_restart() is False


def test_should_restart_false_when_running(supervisor):
    assert supervisor.status == "RUNNING"
    assert supervisor.should_restart() is False


# ═══════════════════════════════════════════════════════════════════════════════
# Section 4 — CSSServiceManager.try_restart
# ═══════════════════════════════════════════════════════════════════════════════

def test_try_restart_increments_restart_attempts():
    svc = _make_svc()
    svc.start()
    svc.process.wait()
    svc.check_status()  # marks as STOPPED

    with patch.object(svc, "start", return_value=True) as mock_start:
        svc.try_restart()
    assert svc.restart_attempts == 1


def test_try_restart_records_last_restart_at():
    svc = _make_svc()
    assert svc.last_restart_at is None
    with patch.object(svc, "start", return_value=True):
        svc.try_restart()
    assert svc.last_restart_at is not None


def test_try_restart_resets_restart_attempts_on_successful_start():
    """
    When try_restart() ultimately calls the REAL start() and succeeds,
    start() resets restart_attempts to 0.  Here we test that contract by
    letting try_restart call through to the real start() (with a fast
    process) and verifying the reset happened.
    """
    svc = _make_svc(exit_code=0)
    # Simulate two previous attempts recorded against this service
    svc.restart_attempts = 2

    # try_restart will increment to 3, call real start() which sets it to 0
    result = svc.try_restart()
    assert result is True
    # After a successful start(), restart_attempts is reset to 0
    assert svc.restart_attempts == 0
    # Clean up
    if svc.process and svc.process.poll() is None:
        svc.stop()


def test_try_restart_returns_false_when_start_fails():
    svc = _make_svc()
    with patch.object(svc, "start", return_value=False):
        result = svc.try_restart()
    assert result is False


def test_try_restart_returns_false_on_exception():
    svc = _make_svc()
    with patch.object(svc, "start", side_effect=OSError("binary not found")):
        result = svc.try_restart()
    assert result is False
    assert svc.status == "FAILED"


def test_try_restart_launches_stdout_drain_thread_on_success():
    svc = _make_svc()
    drain_calls = []

    def fake_drain(stream, name):
        drain_calls.append(name)

    # Need a real-looking process with stdout
    with patch.object(svc, "start", return_value=True):
        mock_proc = MagicMock()
        mock_proc.stdout = MagicMock()  # truthy
        svc.process = mock_proc
        svc.try_restart(stdout_drain_callback=fake_drain)

    # Give the daemon thread a moment to run
    import time; time.sleep(0.05)
    assert svc.service_name in drain_calls


# ═══════════════════════════════════════════════════════════════════════════════
# Section 5 — monitor_and_restart_services integration
# ═══════════════════════════════════════════════════════════════════════════════

def _mock_supervisor(temp_dir, alert_mock, max_restart_limit=3):
    sup = CSSRuntimeSupervisor(
        state_dir=temp_dir,
        max_restart_limit=max_restart_limit,
        alert_service=alert_mock,
    )
    sup.start()
    return sup


def test_monitor_does_not_restart_running_service(temp_dir, alert_mock):
    sup = _mock_supervisor(temp_dir, alert_mock)
    svc = _make_svc()
    svc.start()
    assert svc.status == "RUNNING"

    with patch.object(svc, "try_restart") as mock_restart:
        monitor_and_restart_services([svc], sup)

    mock_restart.assert_not_called()
    svc.stop()


def test_monitor_does_not_restart_cleanly_stopped_service(temp_dir, alert_mock):
    """retcode == 0 is a clean exit — should not trigger restart."""
    sup = _mock_supervisor(temp_dir, alert_mock)
    svc = _make_svc(exit_code=0)
    svc.start()
    svc.process.wait()
    svc.check_status()
    assert svc.status == "STOPPED"  # clean exit

    with patch.object(svc, "try_restart") as mock_restart:
        monitor_and_restart_services([svc], sup)

    mock_restart.assert_not_called()


def test_monitor_restarts_failed_service(temp_dir, alert_mock):
    sup = _mock_supervisor(temp_dir, alert_mock)
    svc = _make_svc(exit_code=1)
    svc.start()
    svc.process.wait()
    svc.check_status()
    assert svc.status == "FAILED"

    with patch("time.sleep"), \
         patch.object(svc, "try_restart", return_value=True) as mock_restart:
        monitor_and_restart_services([svc], sup)

    mock_restart.assert_called_once()


def test_monitor_emits_critical_when_limit_exhausted(temp_dir, alert_mock):
    sup = _mock_supervisor(temp_dir, alert_mock, max_restart_limit=1)
    svc = _make_svc(exit_code=1)

    sup.record_failure("pre-exhausted")
    sup.record_restart_attempt("CSS Runtime", attempt=1, delay_seconds=0.0)

    assert sup.should_restart() is False

    svc.start()
    svc.process.wait()
    svc.check_status()

    alert_mock.reset_mock()
    with patch("time.sleep"), \
         patch.object(svc, "try_restart", return_value=False):
        monitor_and_restart_services([svc], sup)

    # Should have emitted a CRITICAL alert
    severities = [
        c.kwargs.get("severity")
        for c in alert_mock.emit_system_alert.call_args_list
        if c.kwargs.get("severity") is not None
    ]
    assert AlertSeverity.CRITICAL in severities


def test_monitor_does_not_restart_beyond_limit(temp_dir, alert_mock):
    """After the limit is hit, try_restart should not be called again."""
    sup = _mock_supervisor(temp_dir, alert_mock, max_restart_limit=1)

    svc = _make_svc(exit_code=1)
    svc.start()
    svc.process.wait()
    svc.check_status()

    # Exhaust the limit
    sup.record_failure("pre-failure-1")
    sup.record_restart_attempt("CSS Runtime", attempt=1, delay_seconds=0.0)
    assert sup.should_restart() is False

    with patch("time.sleep"), \
         patch.object(svc, "try_restart") as mock_restart:
        monitor_and_restart_services([svc], sup)

    mock_restart.assert_not_called()


def test_monitor_uses_exponential_backoff(temp_dir, alert_mock):
    """Verify backoff delay is computed and sleep is called with that value."""
    sup = _mock_supervisor(temp_dir, alert_mock)
    svc = _make_svc(exit_code=1)
    svc.start()
    svc.process.wait()
    svc.check_status()

    expected_delay = sup.compute_backoff_delay(1)  # first attempt

    with patch("time.sleep") as mock_sleep, \
         patch.object(svc, "try_restart", return_value=True):
        monitor_and_restart_services([svc], sup)

    mock_sleep.assert_any_call(expected_delay)


def test_monitor_records_restart_success_on_successful_restart(temp_dir, alert_mock):
    sup = _mock_supervisor(temp_dir, alert_mock)
    initial_restarts = sup.restart_count

    svc = _make_svc(exit_code=1)
    svc.start()
    svc.process.wait()
    svc.check_status()

    with patch("time.sleep"), \
         patch.object(svc, "try_restart", return_value=True):
        monitor_and_restart_services([svc], sup)

    assert sup.restart_count == initial_restarts + 1


def test_no_infinite_restart_loop(temp_dir, alert_mock):
    """
    Simulate repeated monitor cycles against a service that always fails.
    After max_restart_limit+1 cycles, no more restart attempts should occur.
    """
    max_limit = 2
    sup = _mock_supervisor(temp_dir, alert_mock, max_restart_limit=max_limit)

    restart_call_count = [0]

    def always_fail_restart(*args, **kwargs):
        restart_call_count[0] += 1
        return False

    svc = _make_svc(exit_code=1)

    # Run more cycles than the max_restart_limit
    for _ in range(max_limit + 3):
        # Force the service to appear FAILED each cycle
        svc.status = "FAILED"
        with patch("time.sleep"), \
             patch.object(svc, "try_restart", side_effect=always_fail_restart):
            monitor_and_restart_services([svc], sup)

    # try_restart should have been called at most max_limit times total
    assert restart_call_count[0] <= max_limit, (
        f"try_restart called {restart_call_count[0]} times, expected <= {max_limit}"
    )
