import os
import sys
import pytest

from launcher.css_service_manager import CSSServiceManager
from launcher.css_runtime_launcher import check_environment, duplicate_canonical_runtime_owners

def test_css_service_manager_lifecycle():
    # Use a simple cross-platform command that exits quickly
    cmd = [sys.executable, "-c", "print('Hello World')"]
    svc = CSSServiceManager("Test Service", cmd, os.getcwd())
    
    assert svc.status == "STOPPED"
    
    # Start service
    started = svc.start()
    assert started is True
    assert svc.status == "RUNNING"
    assert svc.pid is not None
    
    # Wait for it to finish
    svc.process.wait()
    
    # Check status again
    status = svc.check_status()
    assert status == "STOPPED"
    assert svc.pid is None
    
def test_css_service_manager_failure():
    # A command that intentionally fails
    cmd = [sys.executable, "-c", "import sys; sys.exit(1)"]
    svc = CSSServiceManager("Fail Service", cmd, os.getcwd())
    
    svc.start()
    svc.process.wait()
    
    status = svc.check_status()
    assert status == "FAILED"

def test_css_service_manager_stop():
    # A command that sleeps
    cmd = [sys.executable, "-c", "import time; time.sleep(10)"]
    svc = CSSServiceManager("Sleep Service", cmd, os.getcwd())
    
    svc.start()
    assert svc.status == "RUNNING"
    
    svc.stop()
    assert svc.status == "STOPPED"
    assert svc.pid is None

def test_check_environment_fails_when_port_in_use(monkeypatch):
    import socket
    # Mock is_port_in_use to True
    monkeypatch.setattr("launcher.css_runtime_launcher.is_port_in_use", lambda p: True)
    monkeypatch.setattr(
        "launcher.css_runtime_launcher.duplicate_canonical_runtime_owners",
        lambda: {"ok": True, "owners": [], "error_code": None},
    )
    
    # Even if files exist, port check should fail it
    assert check_environment() is False


def test_check_environment_fails_when_duplicate_canonical_owner(monkeypatch):
    monkeypatch.setattr("launcher.css_runtime_launcher.is_port_in_use", lambda p: False)
    monkeypatch.setattr(
        "launcher.css_runtime_launcher.duplicate_canonical_runtime_owners",
        lambda: {"ok": True, "owners": [{"pid": 4242, "role": "canonical_launcher"}], "error_code": None},
    )

    assert check_environment() is False


def test_check_environment_fails_when_discovery_not_ok(monkeypatch):
    monkeypatch.setattr("launcher.css_runtime_launcher.is_port_in_use", lambda p: False)
    monkeypatch.setattr(
        "launcher.css_runtime_launcher.duplicate_canonical_runtime_owners",
        lambda: {"ok": False, "owners": [], "error_code": "discovery_exception"},
    )

    assert check_environment() is False


def test_duplicate_owner_filters_to_canonical_launcher(monkeypatch, tmp_path):
    rows = [
        {
            "pid": 100,
            "role": "canonical_launcher",
        },
        {
            "pid": 101,
            "role": "managed_child",
        },
    ]
    monkeypatch.setattr(
        "launcher.css_runtime_launcher.discover_canonical_runtime_processes",
        lambda **_: {"ok": True, "processes": rows, "error_code": None, "error_type": None},
    )

    result = duplicate_canonical_runtime_owners(repo_root=str(tmp_path))
    assert result["ok"] is True
    assert result["owners"] == [rows[0]]


def test_run_launcher_cleans_started_children_on_identity_failure(monkeypatch):
    import launcher.css_runtime_launcher as launcher

    events = []
    services = []

    class FakeSupervisor:
        def start(self):
            events.append("supervisor_start")

        def stop(self):
            events.append("supervisor_stop")

    class FakeService:
        def __init__(self, service_name, *_args, **_kwargs):
            self.service_name = service_name
            self.process = None
            services.append(self)

        def start(self):
            events.append(f"start:{self.service_name}")
            return True

        def stop(self):
            events.append(f"stop:{self.service_name}")

    monkeypatch.setattr(launcher, "check_environment", lambda: True)
    monkeypatch.setattr(launcher, "CSSRuntimeSupervisor", FakeSupervisor)
    monkeypatch.setattr(launcher, "CSSServiceManager", FakeService)
    monkeypatch.setattr(
        launcher,
        "_record_strong_process_tree",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("identity failed")),
    )

    with pytest.raises(RuntimeError, match="identity failed"):
        launcher.run_launcher()

    assert len(services) == 2
    assert events == [
        "supervisor_start",
        "start:CSS Runtime",
        "start:Mobile Launcher",
        "stop:CSS Runtime",
        "stop:Mobile Launcher",
        "supervisor_stop",
    ]
