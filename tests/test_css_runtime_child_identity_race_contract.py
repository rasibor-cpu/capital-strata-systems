from __future__ import annotations

from types import SimpleNamespace

import pytest

from launcher import css_runtime_launcher as runtime_launcher


class _Service:
    def __init__(self, *, status: str, pid: int | None, exit_code: int | None):
        self.service_name = "CSS Runtime"
        self.status = status
        self.pid = pid
        self.process = SimpleNamespace(poll=lambda: exit_code)

    def check_status(self):
        if self.status == "RUNNING" and self.process.poll() is not None:
            self.status = "STOPPED" if self.process.poll() == 0 else "FAILED"
            self.pid = None
        return self.status

    def get_info(self):
        return {
            "service_name": self.service_name,
            "pid": self.pid,
            "status": self.status,
            "started_at": "2026-09-25T12:00:00+00:00",
            "restart_count": 0,
            "restart_attempts": 0,
            "last_restart_at": None,
        }


def test_clean_child_exit_during_identity_capture_is_recorded_not_running(monkeypatch):
    service = _Service(status="RUNNING", pid=1234, exit_code=0)

    def should_not_probe(*args, **kwargs):
        raise AssertionError("identity probe must not run for a proven stopped child")

    monkeypatch.setattr(runtime_launcher, "_live_process_fields", should_not_probe)
    info = runtime_launcher._service_identity_info(service)

    assert info["status"] == "STOPPED"
    assert info["pid"] is None
    assert info["identity_status"] == "NOT_RUNNING"
    assert info["process_exit_code"] == 0
    assert info["executable_path"] is None


def test_running_child_missing_live_identity_remains_fail_closed(monkeypatch):
    service = _Service(status="RUNNING", pid=1234, exit_code=None)

    def unavailable(pid, *, role):
        raise RuntimeError(f"process_identity_unavailable:{role}")

    monkeypatch.setattr(runtime_launcher, "_live_process_fields", unavailable)

    with pytest.raises(RuntimeError, match="process_identity_unavailable:CSS Runtime"):
        runtime_launcher._service_identity_info(service)
