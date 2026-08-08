import json
import os
import sys
from types import SimpleNamespace

import pytest

from launcher.css_service_manager import CSSServiceManager
from launcher.css_runtime_launcher import (
    DISCOVERY_SCHEMA,
    check_environment,
    discover_canonical_runtime_processes,
    duplicate_canonical_runtime_owners,
)


def _fake_powershell(stdout: str, returncode: int = 0):
    def _run(*_args, **_kwargs):
        return SimpleNamespace(returncode=returncode, stdout=stdout, stderr="")

    return _run


def _envelope(processes, *, anchor_pid=4242, ok=True, self_observed=True) -> str:
    return json.dumps(
        {
            "schema_version": DISCOVERY_SCHEMA,
            "ok": ok,
            "anchor_pid": anchor_pid,
            "self_observed": self_observed,
            "processes": processes,
            "error_code": None,
            "error_type": None,
        }
    )


def _row(
    *,
    pid=99,
    parent_pid=1,
    creation_date="20260801000000.000000+000",
    executable_path=None,
    command_line="python other.py",
):
    return {
        "ProcessId": pid,
        "ParentProcessId": parent_pid,
        "CreationDate": creation_date,
        "ExecutablePath": executable_path or sys.executable,
        "CommandLine": command_line,
    }


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


def test_discovery_empty_stdout_fails_closed(monkeypatch):
    monkeypatch.setattr("launcher.css_runtime_launcher.subprocess.run", _fake_powershell("   \n "))
    result = discover_canonical_runtime_processes(current_pid=4242)
    assert result["ok"] is False
    assert result["error_code"] == "discovery_empty_output"
    assert result["processes"] == []


def test_discovery_empty_json_array_without_self_fails_closed(monkeypatch):
    monkeypatch.setattr("launcher.css_runtime_launcher.subprocess.run", _fake_powershell("[]"))
    result = discover_canonical_runtime_processes(current_pid=4242)
    assert result["ok"] is False
    assert result["error_code"] == "discovery_envelope_malformed"
    assert result["processes"] == []


def test_discovery_envelope_without_self_or_anchor_fails_closed(monkeypatch, tmp_path):
    payload = _envelope(
        [_row()],
        anchor_pid=7,
    )
    monkeypatch.setattr("launcher.css_runtime_launcher.subprocess.run", _fake_powershell(payload))
    result = discover_canonical_runtime_processes(repo_root=str(tmp_path), current_pid=4242)
    assert result["ok"] is False
    assert result["error_code"] == "discovery_anchor_mismatch"


def test_discovery_anchor_pid_satisfies_self_observation(monkeypatch, tmp_path):
    payload = _envelope(
        [_row()],
        anchor_pid=4242,
    )
    monkeypatch.setattr("launcher.css_runtime_launcher.subprocess.run", _fake_powershell(payload))
    result = discover_canonical_runtime_processes(repo_root=str(tmp_path), current_pid=4242)
    assert result["ok"] is True
    assert result["self_observed"] is True
    assert result["processes"] == []


def test_discovery_zero_managed_processes_after_self_filter_is_ok(monkeypatch, tmp_path):
    payload = _envelope(
        [_row(pid=4242, command_line="python launcher")],
    )
    monkeypatch.setattr("launcher.css_runtime_launcher.subprocess.run", _fake_powershell(payload))
    result = discover_canonical_runtime_processes(repo_root=str(tmp_path), current_pid=4242)
    assert result["ok"] is True
    assert result["processes"] == []
    assert result["error_code"] is None


def test_discovery_finds_other_canonical_owner(monkeypatch, tmp_path):
    other_cmd = f"python {tmp_path}\\launcher\\css_runtime_launcher.py"
    payload = _envelope(
        [
            _row(pid=4242, command_line="python self"),
            _row(pid=99, command_line=other_cmd),
        ]
    )
    monkeypatch.setattr("launcher.css_runtime_launcher.subprocess.run", _fake_powershell(payload))
    result = discover_canonical_runtime_processes(repo_root=str(tmp_path), current_pid=4242)
    assert result["ok"] is True
    assert [row["pid"] for row in result["processes"]] == [99]
    assert result["processes"][0]["role"] == "canonical_launcher"

    owners = duplicate_canonical_runtime_owners(repo_root=str(tmp_path), current_pid=4242)
    assert owners["ok"] is True
    assert [row["pid"] for row in owners["owners"]] == [99]


def test_discovery_duplicate_keys_fail_closed(monkeypatch):
    monkeypatch.setattr(
        "launcher.css_runtime_launcher.subprocess.run",
        _fake_powershell('{"ok":true,"processes":[],"processes":[]}'),
    )
    result = discover_canonical_runtime_processes(current_pid=4242)
    assert result["ok"] is False
    assert result["error_code"] == "discovery_output_unreadable"


def test_discovery_malformed_envelope_fails_closed(monkeypatch):
    monkeypatch.setattr(
        "launcher.css_runtime_launcher.subprocess.run",
        _fake_powershell('{"ok":true,"processes":"not-a-list"}'),
    )
    result = discover_canonical_runtime_processes(current_pid=4242)
    assert result["ok"] is False
    assert result["error_code"] == "discovery_envelope_fields_mismatch"


def test_discovery_failed_envelope_never_becomes_success(monkeypatch):
    monkeypatch.setattr(
        "launcher.css_runtime_launcher.subprocess.run",
        _fake_powershell(_envelope([], ok=False)),
    )
    result = discover_canonical_runtime_processes(current_pid=4242)
    assert result["ok"] is False
    assert result["error_code"] == "discovery_reported_failure"


@pytest.mark.parametrize(
    ("field", "value", "error_code"),
    [
        ("ProcessId", True, "discovery_pid_malformed"),
        ("ProcessId", 0, "discovery_pid_malformed"),
        ("ProcessId", -1, "discovery_pid_malformed"),
        ("ProcessId", 2**32, "discovery_pid_malformed"),
        ("ProcessId", "99", "discovery_pid_malformed"),
        ("ParentProcessId", False, "discovery_parent_pid_malformed"),
        ("ParentProcessId", 0, "discovery_parent_pid_malformed"),
        ("ParentProcessId", -1, "discovery_parent_pid_malformed"),
        ("ParentProcessId", 2**32, "discovery_parent_pid_malformed"),
        ("ParentProcessId", "1", "discovery_parent_pid_malformed"),
        ("CreationDate", None, "discovery_row_fields_mismatch"),
        ("CreationDate", "", "discovery_row_fields_mismatch"),
        ("CreationDate", [], "discovery_row_fields_mismatch"),
        ("CreationDate", "not-a-date", "discovery_creation_malformed"),
        ("ExecutablePath", None, "discovery_row_fields_mismatch"),
        ("ExecutablePath", "", "discovery_row_fields_mismatch"),
        ("ExecutablePath", [], "discovery_row_fields_mismatch"),
        ("CommandLine", None, "discovery_command_unavailable"),
        ("CommandLine", "", "discovery_command_unavailable"),
        ("CommandLine", [], "discovery_command_unavailable"),
    ],
)
def test_discovery_process_row_field_matrix_fails_closed(monkeypatch, field, value, error_code):
    row = _row(command_line="python c:/repo/launcher/css_runtime_launcher.py")
    row[field] = value
    monkeypatch.setattr("launcher.css_runtime_launcher.subprocess.run", _fake_powershell(_envelope([row])))
    result = discover_canonical_runtime_processes(repo_root="c:/repo", current_pid=4242)
    assert result["ok"] is False
    assert result["error_code"] == error_code


@pytest.mark.parametrize("missing", ["ProcessId", "ParentProcessId", "CreationDate", "ExecutablePath", "CommandLine"])
def test_discovery_process_row_missing_field_fails_closed(monkeypatch, missing):
    row = _row(command_line="python c:/repo/launcher/css_runtime_launcher.py")
    row.pop(missing)
    monkeypatch.setattr("launcher.css_runtime_launcher.subprocess.run", _fake_powershell(_envelope([row])))
    result = discover_canonical_runtime_processes(repo_root="c:/repo", current_pid=4242)
    assert result["ok"] is False
    assert result["error_code"] == "discovery_row_fields_mismatch"


def test_discovery_partial_process_row_exploit_fails_closed(monkeypatch):
    row = {"ProcessId": 99, "CommandLine": "python c:/repo/launcher/css_runtime_launcher.py"}
    monkeypatch.setattr("launcher.css_runtime_launcher.subprocess.run", _fake_powershell(_envelope([row])))
    result = discover_canonical_runtime_processes(repo_root="c:/repo", current_pid=4242)
    assert result["ok"] is False
    assert result["error_code"] == "discovery_row_fields_mismatch"


@pytest.mark.parametrize(
    "duplicate",
    [
        _row(pid=99, command_line="python c:/repo/launcher/css_runtime_launcher.py"),
        _row(pid=99, command_line="python c:/repo/launcher/css_mobile_launcher.py"),
        _row(
            pid=99,
            executable_path="C:/other/python.exe",
            command_line="python c:/repo/launcher/css_runtime_launcher.py",
        ),
        _row(
            pid=99,
            creation_date="20260801000100.000000+000",
            command_line="python c:/repo/launcher/css_runtime_launcher.py",
        ),
        _row(pid=99, command_line="python c:/repo/launcher/css_runtime_launcher.py --second"),
        _row(pid=99, parent_pid=2, command_line="python c:/repo/launcher/css_runtime_launcher.py"),
    ],
)
def test_discovery_duplicate_process_rows_fail_closed(monkeypatch, duplicate):
    first = _row(pid=99, command_line="python c:/repo/launcher/css_runtime_launcher.py")
    monkeypatch.setattr(
        "launcher.css_runtime_launcher.subprocess.run",
        _fake_powershell(_envelope([_row(pid=4242, command_line="python self"), first, duplicate])),
    )
    result = discover_canonical_runtime_processes(repo_root="c:/repo", current_pid=4242)
    assert result["ok"] is False
    assert result["error_code"] == "discovery_duplicate_process_id"


def test_discovery_duplicate_pid_mixed_valid_invalid_fails_closed(monkeypatch):
    rows = [
        _row(pid=4242, command_line="python self"),
        _row(pid=99, command_line="python c:/repo/launcher/css_runtime_launcher.py"),
        _row(pid="99", command_line="python c:/repo/launcher/css_runtime_launcher.py"),
    ]
    monkeypatch.setattr("launcher.css_runtime_launcher.subprocess.run", _fake_powershell(_envelope(rows)))
    result = discover_canonical_runtime_processes(repo_root="c:/repo", current_pid=4242)
    assert result["ok"] is False
    assert result["error_code"] == "discovery_pid_malformed"


def test_discovery_duplicate_canonical_runtime_identities_fail_closed(monkeypatch):
    rows = [
        _row(pid=4242, command_line="python self"),
        _row(pid=99, command_line="python c:/repo/launcher/css_runtime_launcher.py"),
        _row(pid=100, command_line="python c:/repo/launcher/css_runtime_launcher.py --second"),
    ]
    monkeypatch.setattr("launcher.css_runtime_launcher.subprocess.run", _fake_powershell(_envelope(rows)))
    result = discover_canonical_runtime_processes(repo_root="c:/repo", current_pid=4242)
    assert result["ok"] is False
    assert result["error_code"] == "discovery_duplicate_canonical_identity"


@pytest.mark.parametrize(
    ("command_line", "expected_role"),
    [
        ("python c:/repo/launcher/css_runtime_launcher.py", "canonical_launcher"),
        ("python c:/repo/launcher/css_mobile_launcher.py", "managed_child"),
    ],
)
def test_discovery_single_runtime_role_classification_succeeds(monkeypatch, command_line, expected_role):
    rows = [
        _row(pid=4242, command_line="python self"),
        _row(pid=99, command_line=command_line),
    ]
    monkeypatch.setattr("launcher.css_runtime_launcher.subprocess.run", _fake_powershell(_envelope(rows)))
    result = discover_canonical_runtime_processes(repo_root="c:/repo", current_pid=4242)
    assert result["ok"] is True
    assert [(row["pid"], row["role"]) for row in result["processes"]] == [(99, expected_role)]


@pytest.mark.parametrize(
    "command_line",
    [
        "python c:/repo/launcher/css_runtime_launcher.py c:/repo/launcher/css_mobile_launcher.py",
        "python -m launcher.css_runtime_launcher c:/repo/scripts/css_live_dashboard.py",
    ],
)
def test_discovery_conflicting_runtime_role_classification_fails_closed(monkeypatch, command_line):
    rows = [
        _row(pid=4242, command_line="python self"),
        _row(pid=99, command_line=command_line),
    ]
    monkeypatch.setattr("launcher.css_runtime_launcher.subprocess.run", _fake_powershell(_envelope(rows)))
    result = discover_canonical_runtime_processes(repo_root="c:/repo", current_pid=4242)
    assert result["ok"] is False
    assert result["error_code"] == "discovery_conflicting_role_classification"


def test_discovery_duplicate_conflicting_role_combinations_fail_closed(monkeypatch):
    rows = [
        _row(pid=4242, command_line="python self"),
        _row(pid=99, command_line="python c:/repo/launcher/css_runtime_launcher.py c:/repo/launcher/css_mobile_launcher.py"),
        _row(pid=100, command_line="python c:/repo/launcher/css_runtime_launcher.py c:/repo/launcher/css_mobile_launcher.py"),
    ]
    monkeypatch.setattr("launcher.css_runtime_launcher.subprocess.run", _fake_powershell(_envelope(rows)))
    result = discover_canonical_runtime_processes(repo_root="c:/repo", current_pid=4242)
    assert result["ok"] is False
    assert result["error_code"] == "discovery_conflicting_role_classification"


def test_discovery_unique_valid_launcher_and_child_rows_still_succeed(monkeypatch):
    rows = [
        _row(pid=4242, command_line="python self"),
        _row(pid=99, command_line="python c:/repo/launcher/css_runtime_launcher.py"),
        _row(pid=100, command_line="python c:/repo/launcher/css_mobile_launcher.py"),
    ]
    monkeypatch.setattr("launcher.css_runtime_launcher.subprocess.run", _fake_powershell(_envelope(rows)))
    result = discover_canonical_runtime_processes(repo_root="c:/repo", current_pid=4242)
    assert result["ok"] is True
    assert [(row["pid"], row["role"]) for row in result["processes"]] == [
        (99, "canonical_launcher"),
        (100, "managed_child"),
    ]


def test_duplicate_owners_propagate_self_missing(monkeypatch):
    monkeypatch.setattr("launcher.css_runtime_launcher.subprocess.run", _fake_powershell("[]"))
    owners = duplicate_canonical_runtime_owners(current_pid=4242)
    assert owners["ok"] is False
    assert owners["error_code"] == "discovery_envelope_malformed"
    assert owners["owners"] == []


def test_run_launcher_cleans_started_children_on_identity_failure(monkeypatch):
    import launcher.css_runtime_launcher as launcher

    events = []
    services = []

    class FakeSupervisor:
        def __init__(self, *_args, **_kwargs):
            pass

        def start(self):
            events.append("supervisor_start")

        def stop(self):
            events.append("supervisor_stop")

        def record_identity_verification_failure(self, reason_code, *, detail_code=None):
            events.append(f"identity_verification_failed:{reason_code}")

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
        "identity_verification_failed:strong_process_identity_unavailable",
        "stop:CSS Runtime",
        "stop:Mobile Launcher",
        "supervisor_stop",
    ]


def test_discovery_ignores_inline_python_mentions_but_detects_real_invocations_r6(monkeypatch):
    rows = [
        _row(pid=4242, command_line="python self"),
        _row(
            pid=1001,
            command_line="python -c import_launcher.css_runtime_launcher_c:/repo/launcher/css_runtime_launcher.py",
        ),
        _row(pid=1002, command_line="python c:/repo/launcher/css_runtime_launcher.py"),
        _row(pid=1003, parent_pid=1002, command_line="python c:/repo/scripts/css_live_dashboard.py"),
    ]
    monkeypatch.setattr(
        "launcher.css_runtime_launcher.subprocess.run",
        _fake_powershell(_envelope(rows)),
    )
    result = discover_canonical_runtime_processes(repo_root="c:/repo", current_pid=4242)
    assert result["ok"] is True
    by_pid = {row["pid"]: row for row in result["processes"]}
    assert 1001 not in by_pid
    assert by_pid[1002]["role"] == "canonical_launcher"
    assert by_pid[1003]["role"] == "managed_child"


def test_discovery_detects_module_launcher_invocation_r6(monkeypatch):
    rows = [
        _row(pid=4242, command_line="python self"),
        _row(pid=2001, command_line="python -m launcher.css_runtime_launcher c:/repo"),
    ]
    monkeypatch.setattr(
        "launcher.css_runtime_launcher.subprocess.run",
        _fake_powershell(_envelope(rows)),
    )
    result = discover_canonical_runtime_processes(repo_root="c:/repo", current_pid=4242)
    assert result["ok"] is True
    assert [(row["pid"], row["role"]) for row in result["processes"]] == [
        (2001, "canonical_launcher")
    ]
