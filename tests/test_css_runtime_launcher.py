import json
import os
import sys
from types import SimpleNamespace

import pytest

from launcher.css_service_manager import CSSServiceManager
from launcher.css_runtime_launcher import (
    check_environment,
    classify_canonical_process_command,
    discover_canonical_runtime_processes,
    duplicate_canonical_runtime_owners,
    is_proven_non_owner_wrapper,
)
import launcher.css_runtime_launcher as runtime_launcher


def test_css_service_manager_lifecycle():
    cmd = [sys.executable, "-c", "print('Hello World')"]
    svc = CSSServiceManager("Test Service", cmd, os.getcwd())

    assert svc.status == "STOPPED"

    started = svc.start()
    assert started is True
    assert svc.status == "RUNNING"
    assert svc.pid is not None

    svc.process.wait()

    status = svc.check_status()
    assert status == "STOPPED"
    assert svc.pid is None


def test_css_service_manager_failure():
    cmd = [sys.executable, "-c", "import sys; sys.exit(1)"]
    svc = CSSServiceManager("Fail Service", cmd, os.getcwd())

    svc.start()
    svc.process.wait()

    status = svc.check_status()
    assert status == "FAILED"


def test_css_service_manager_stop():
    cmd = [sys.executable, "-c", "import time; time.sleep(10)"]
    svc = CSSServiceManager("Sleep Service", cmd, os.getcwd())

    svc.start()
    assert svc.status == "RUNNING"

    svc.stop()
    assert svc.status == "STOPPED"
    assert svc.pid is None


def test_check_environment_fails_when_port_in_use(monkeypatch):
    monkeypatch.setattr("launcher.css_runtime_launcher.is_port_in_use", lambda p: True)
    monkeypatch.setattr(
        "launcher.css_runtime_launcher.duplicate_canonical_runtime_owners",
        lambda: {"ok": True, "owners": [], "error_code": None, "error_type": None},
    )

    assert check_environment() is False


def test_check_environment_fails_when_duplicate_canonical_owner(monkeypatch):
    monkeypatch.setattr("launcher.css_runtime_launcher.is_port_in_use", lambda p: False)
    monkeypatch.setattr(
        "launcher.css_runtime_launcher.duplicate_canonical_runtime_owners",
        lambda: {
            "ok": True,
            "owners": [{"pid": 4242, "role": "canonical_launcher"}],
            "error_code": None,
            "error_type": None,
        },
    )

    assert check_environment() is False


def test_check_environment_fails_when_discovery_fails(monkeypatch):
    monkeypatch.setattr("launcher.css_runtime_launcher.is_port_in_use", lambda p: False)
    monkeypatch.setattr(
        "launcher.css_runtime_launcher.duplicate_canonical_runtime_owners",
        lambda: {
            "ok": False,
            "owners": [],
            "error_code": "discovery_powershell_failed",
            "error_type": "subprocess_error",
        },
    )

    assert check_environment() is False


def test_duplicate_owner_filters_to_canonical_launcher(monkeypatch, tmp_path):
    rows = [
        {
            "pid": 100,
            "role": "canonical_launcher",
            "command_line": str(tmp_path / "launcher" / "css_runtime_launcher.py"),
        },
        {
            "pid": 101,
            "role": "managed_child",
            "command_line": str(tmp_path / "launcher" / "css_mobile_launcher.py"),
        },
    ]
    monkeypatch.setattr(
        "launcher.css_runtime_launcher.discover_canonical_runtime_processes",
        lambda **_: {
            "ok": True,
            "processes": rows,
            "error_code": None,
            "error_type": None,
        },
    )

    result = duplicate_canonical_runtime_owners(repo_root=str(tmp_path))
    assert result["ok"] is True
    assert result["owners"] == [rows[0]]


def _patch_windows_discovery(monkeypatch, process_rows, *, returncode=0, raw=None):
    monkeypatch.setattr(runtime_launcher.os, "name", "nt")

    if raw is None:
        payload = {
            "schema_version": runtime_launcher.DISCOVERY_SCHEMA,
            "ok": True,
            "processes": process_rows,
            "error_code": None,
        }
        raw = json.dumps(payload)

    monkeypatch.setattr(
        runtime_launcher.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            stdout=raw,
            stderr="",
            returncode=returncode,
        ),
    )


def test_parent_canonical_launcher_remains_visible(monkeypatch, tmp_path):
    repo = str(tmp_path)
    parent_cmd = f'"{sys.executable}" -m launcher.css_runtime_launcher "{repo}"'
    child_cmd = f'"{sys.executable}" -m launcher.css_runtime_launcher "{repo}" CHILD'

    process_rows = [
        {"ProcessId": 777, "ParentProcessId": 1, "CommandLine": parent_cmd},
        {"ProcessId": 888, "ParentProcessId": 777, "CommandLine": child_cmd},
    ]
    _patch_windows_discovery(monkeypatch, process_rows)

    # Discovering from the child must still see the parent owner.
    discovery = discover_canonical_runtime_processes(repo_root=repo, current_pid=888)
    assert discovery["ok"] is True
    by_pid = {row["pid"]: row for row in discovery["processes"]}
    assert 777 in by_pid
    assert by_pid[777]["role"] == "canonical_launcher"
    assert 888 not in by_pid  # self skipped


def test_nested_parent_child_duplicate_owners_fail_closed(monkeypatch, tmp_path):
    repo = str(tmp_path)
    parent_cmd = f'"{sys.executable}" -m launcher.css_runtime_launcher "{repo}"'
    child_cmd = f'"{sys.executable}" -m launcher.css_runtime_launcher "{repo}" CHILD'

    process_rows = [
        {"ProcessId": 777, "ParentProcessId": 1, "CommandLine": parent_cmd},
        {"ProcessId": 888, "ParentProcessId": 777, "CommandLine": child_cmd},
    ]
    _patch_windows_discovery(monkeypatch, process_rows)

    owners = duplicate_canonical_runtime_owners(repo_root=repo, current_pid=888)
    assert owners["ok"] is True
    assert [row["pid"] for row in owners["owners"]] == [777]

    monkeypatch.setattr(
        "launcher.css_runtime_launcher.is_port_in_use", lambda p: False
    )
    monkeypatch.setattr(
        "launcher.css_runtime_launcher.duplicate_canonical_runtime_owners",
        lambda: owners,
    )
    assert check_environment() is False


def test_proven_non_owner_wrapper_excluded_by_classification():
    cmd = (
        'C:\\Windows\\System32\\cmd.exe /c '
        'echo launcher.css_runtime_launcher '
        'C:\\repo\\launcher\\css_runtime_launcher.py'
    )
    assert is_proven_non_owner_wrapper(cmd) is True
    assert classify_canonical_process_command(cmd) is None


def test_classify_module_launcher_invocation(tmp_path):
    repo = str(tmp_path)
    cmd = f'"{sys.executable}" -m launcher.css_runtime_launcher "{repo}"'
    assert classify_canonical_process_command(cmd) == "canonical_launcher"


def test_classify_canonical_script_path(tmp_path):
    script = tmp_path / "launcher" / "css_runtime_launcher.py"
    cmd = f'"{sys.executable}" "{script}"'
    assert classify_canonical_process_command(cmd) == "canonical_launcher"


def test_classify_absolute_windows_path(tmp_path):
    script = tmp_path / "launcher" / "css_runtime_launcher.py"
    abs_script = os.path.normcase(str(script))
    cmd = f"{sys.executable} {abs_script}"
    assert classify_canonical_process_command(cmd) == "canonical_launcher"


def test_classify_quoted_canonical_path(tmp_path):
    script = tmp_path / "launcher" / "css_runtime_launcher.py"
    cmd = f"\"{sys.executable}\" \"{script}\""
    assert classify_canonical_process_command(cmd) == "canonical_launcher"


@pytest.mark.parametrize(
    "cmd",
    [
        f'"{sys.executable}" -m foo_launcher.css_runtime_launcher',
        f'"{sys.executable}" script.py --note=launcher.css_runtime_launcher',
        f'"{sys.executable}" C:\\repo\\launcher\\css_runtime_launcher.py.bak',
        f'"{sys.executable}" C:\\repo\\my_css_runtime_launcher.py',
    ],
)
def test_classify_rejects_adversarial_near_matches(cmd):
    assert classify_canonical_process_command(cmd) is None


def test_inline_python_c_diagnostic_rejected_as_owner(tmp_path):
    repo = str(tmp_path)
    cmd = (
        f'"{sys.executable}" -c '
        f'"import launcher.css_runtime_launcher as l; print({repo!r})"'
    )
    assert classify_canonical_process_command(cmd) is None


def test_script_with_c_argument_still_classifies(tmp_path):
    script = tmp_path / "launcher" / "css_runtime_launcher.py"
    cmd = f'"{sys.executable}" "{script}" -c something'
    assert classify_canonical_process_command(cmd) == "canonical_launcher"


def test_discovery_detects_module_and_child(monkeypatch, tmp_path):
    repo = str(tmp_path)
    launcher_script = str(tmp_path / "launcher" / "css_runtime_launcher.py")
    runtime_script = str(tmp_path / "scripts" / "css_live_dashboard.py")

    process_rows = [
        {
            "ProcessId": 1001,
            "ParentProcessId": 50,
            "CommandLine": (
                f'"{sys.executable}" -c '
                f'"import launcher.css_runtime_launcher as l; '
                f'print({launcher_script!r})"'
            ),
        },
        {
            "ProcessId": 1002,
            "ParentProcessId": 50,
            "CommandLine": f'"{sys.executable}" "{launcher_script}"',
        },
        {
            "ProcessId": 1003,
            "ParentProcessId": 1002,
            "CommandLine": f'"{sys.executable}" "{runtime_script}"',
        },
    ]
    _patch_windows_discovery(monkeypatch, process_rows)

    discovery = discover_canonical_runtime_processes(repo_root=repo, current_pid=9999)
    assert discovery["ok"] is True
    by_pid = {row["pid"]: row for row in discovery["processes"]}
    assert 1001 not in by_pid
    assert by_pid[1002]["role"] == "canonical_launcher"
    assert by_pid[1003]["role"] == "managed_child"


def test_enumeration_failure_fails_closed(monkeypatch, tmp_path):
    _patch_windows_discovery(monkeypatch, [], returncode=1, raw="")
    discovery = discover_canonical_runtime_processes(
        repo_root=str(tmp_path), current_pid=1
    )
    assert discovery["ok"] is False
    assert discovery["error_code"] == "discovery_powershell_failed"
    owners = duplicate_canonical_runtime_owners(repo_root=str(tmp_path), current_pid=1)
    assert owners["ok"] is False


def test_malformed_discovery_payload_fails_closed(monkeypatch, tmp_path):
    _patch_windows_discovery(monkeypatch, [], raw="{not-json")
    discovery = discover_canonical_runtime_processes(
        repo_root=str(tmp_path), current_pid=1
    )
    assert discovery["ok"] is False
    assert discovery["error_code"] == "discovery_output_unreadable"


def test_empty_valid_enumeration_means_zero_owners(monkeypatch, tmp_path):
    _patch_windows_discovery(monkeypatch, [])
    discovery = discover_canonical_runtime_processes(
        repo_root=str(tmp_path), current_pid=1
    )
    assert discovery["ok"] is True
    assert discovery["processes"] == []
    owners = duplicate_canonical_runtime_owners(repo_root=str(tmp_path), current_pid=1)
    assert owners["ok"] is True
    assert owners["owners"] == []


def test_duplicate_genuine_owners_reported(monkeypatch, tmp_path):
    repo = str(tmp_path)
    process_rows = [
        {
            "ProcessId": 11,
            "ParentProcessId": 1,
            "CommandLine": f'"{sys.executable}" -m launcher.css_runtime_launcher "{repo}"',
        },
        {
            "ProcessId": 12,
            "ParentProcessId": 1,
            "CommandLine": f'"{sys.executable}" -m launcher.css_runtime_launcher "{repo}" B',
        },
    ]
    _patch_windows_discovery(monkeypatch, process_rows)
    owners = duplicate_canonical_runtime_owners(repo_root=repo, current_pid=99)
    assert owners["ok"] is True
    assert sorted(row["pid"] for row in owners["owners"]) == [11, 12]


def test_empty_stdout_fails_closed(monkeypatch, tmp_path):
    _patch_windows_discovery(monkeypatch, [], returncode=0, raw="   ")
    discovery = discover_canonical_runtime_processes(
        repo_root=str(tmp_path), current_pid=1
    )
    assert discovery["ok"] is False
    assert discovery["error_code"] == "discovery_empty_output"


def test_missing_command_line_rows_are_skipped_not_owners(monkeypatch, tmp_path):
    repo = str(tmp_path)
    process_rows = [
        {"ProcessId": 55, "ParentProcessId": 1, "CommandLine": None},
        {"ProcessId": 56, "ParentProcessId": 1, "CommandLine": ""},
        {
            "ProcessId": 57,
            "ParentProcessId": 1,
            "CommandLine": f'"{sys.executable}" -m launcher.css_runtime_launcher "{repo}"',
        },
    ]
    _patch_windows_discovery(monkeypatch, process_rows)
    discovery = discover_canonical_runtime_processes(repo_root=repo, current_pid=1)
    assert discovery["ok"] is True
    assert [row["pid"] for row in discovery["processes"]] == [57]
