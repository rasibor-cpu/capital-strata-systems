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


def _patch_windows_discovery(
    monkeypatch,
    process_rows,
    *,
    returncode=0,
    raw=None,
    self_observed=True,
    anchor_pid=None,
):
    monkeypatch.setattr(runtime_launcher.os, "name", "nt")

    def _fake_run(*args, **kwargs):
        if raw is not None:
            return SimpleNamespace(stdout=raw, stderr="", returncode=returncode)
        env = kwargs.get("env") or {}
        expected = env.get(runtime_launcher.DISCOVERY_EXPECTED_PID_ENV)
        try:
            expected_i = int(expected) if expected is not None else None
        except (TypeError, ValueError):
            expected_i = None
        resolved_anchor = (
            anchor_pid if anchor_pid is not None else expected_i
        )
        payload = {
            "schema_version": runtime_launcher.DISCOVERY_SCHEMA,
            "ok": True,
            "anchor_pid": resolved_anchor,
            "self_observed": self_observed,
            "processes": process_rows,
            "error_code": None,
            "error_type": None,
        }
        return SimpleNamespace(
            stdout=json.dumps(payload),
            stderr="",
            returncode=returncode,
        )

    monkeypatch.setattr(runtime_launcher.subprocess, "run", _fake_run)


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
    assert discovery["self_observed"] is True
    assert discovery["anchor_pid"] == 1
    assert discovery["expected_pid"] == 1
    owners = duplicate_canonical_runtime_owners(repo_root=str(tmp_path), current_pid=1)
    assert owners["ok"] is True
    assert owners["owners"] == []
    assert owners["self_observed"] is True


def test_missing_self_observed_fails_closed(monkeypatch, tmp_path):
    _patch_windows_discovery(monkeypatch, [], self_observed=False)
    discovery = discover_canonical_runtime_processes(
        repo_root=str(tmp_path), current_pid=1
    )
    assert discovery["ok"] is False
    assert discovery["error_code"] == "discovery_self_missing"
    assert discovery["self_observed"] is False


def test_anchor_mismatch_fails_closed(monkeypatch, tmp_path):
    _patch_windows_discovery(monkeypatch, [], anchor_pid=999)
    discovery = discover_canonical_runtime_processes(
        repo_root=str(tmp_path), current_pid=1
    )
    assert discovery["ok"] is False
    assert discovery["error_code"] == "discovery_anchor_mismatch"


def test_malformed_expected_pid_fails_closed(tmp_path):
    class DerivedPid(int):
        pass

    discovery = discover_canonical_runtime_processes(
        repo_root=str(tmp_path), current_pid=DerivedPid(7)
    )
    assert discovery["ok"] is False
    assert discovery["error_code"] == "discovery_current_pid_malformed"


def test_parent_discovery_reports_anchor_and_self(monkeypatch, tmp_path):
    repo = str(tmp_path)
    parent_cmd = f'"{sys.executable}" -m launcher.css_runtime_launcher "{repo}"'
    child_cmd = f'"{sys.executable}" -m launcher.css_runtime_launcher "{repo}" CHILD'
    process_rows = [
        {"ProcessId": 777, "ParentProcessId": 1, "CommandLine": parent_cmd},
        {"ProcessId": 888, "ParentProcessId": 777, "CommandLine": child_cmd},
    ]
    _patch_windows_discovery(monkeypatch, process_rows)
    discovery = discover_canonical_runtime_processes(repo_root=repo, current_pid=888)
    assert discovery["ok"] is True
    assert discovery["self_observed"] is True
    assert discovery["anchor_pid"] == 888
    assert discovery["expected_pid"] == 888
    assert 777 in {row["pid"] for row in discovery["processes"]}


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


def test_python_exe_canonical_owner_detected(monkeypatch, tmp_path):
    repo = str(tmp_path)
    cmd = f'"C:\\Python312\\python.exe" -m launcher.css_runtime_launcher "{repo}"'
    _patch_windows_discovery(
        monkeypatch,
        [{"ProcessId": 42, "ParentProcessId": 1, "CommandLine": cmd}],
    )
    discovery = discover_canonical_runtime_processes(repo_root=repo, current_pid=1)
    assert discovery["ok"] is True
    assert discovery["processes"][0]["role"] == "canonical_launcher"


def test_pythonw_exe_canonical_owner_detected(monkeypatch, tmp_path):
    repo = str(tmp_path)
    cmd = f'"C:\\Python312\\pythonw.exe" -m launcher.css_runtime_launcher "{repo}"'
    assert classify_canonical_process_command(cmd) == "canonical_launcher"
    _patch_windows_discovery(
        monkeypatch,
        [{"ProcessId": 43, "ParentProcessId": 1, "CommandLine": cmd}],
    )
    discovery = discover_canonical_runtime_processes(repo_root=repo, current_pid=1)
    assert discovery["ok"] is True
    assert [row["pid"] for row in discovery["processes"]] == [43]
    script = runtime_launcher._windows_discovery_command()
    assert "pythonw?" in script or "pythonw" in script.lower()


def test_versioned_python_interpreter_owner_detected(monkeypatch, tmp_path):
    repo = str(tmp_path)
    cmd = f'"C:\\Python312\\python3.12.exe" -m launcher.css_runtime_launcher "{repo}"'
    assert classify_canonical_process_command(cmd) == "canonical_launcher"
    _patch_windows_discovery(
        monkeypatch,
        [{"ProcessId": 44, "ParentProcessId": 1, "CommandLine": cmd}],
    )
    discovery = discover_canonical_runtime_processes(repo_root=repo, current_pid=1)
    assert discovery["ok"] is True
    assert discovery["processes"][0]["pid"] == 44


def test_unsupported_interpreter_does_not_falsely_match():
    cmd = '"C:\\Tools\\notpython.exe" -m launcher.css_runtime_launcher C:\\repo'
    assert classify_canonical_process_command(cmd) is None


def test_discovery_duplicate_process_id_fails_closed(monkeypatch, tmp_path):
    repo = str(tmp_path)
    cmd = f'"{sys.executable}" -m launcher.css_runtime_launcher "{repo}"'
    process_rows = [
        {"ProcessId": 70, "ParentProcessId": 1, "CommandLine": cmd},
        {"ProcessId": 70, "ParentProcessId": 2, "CommandLine": cmd + " B"},
    ]
    _patch_windows_discovery(monkeypatch, process_rows)
    discovery = discover_canonical_runtime_processes(repo_root=repo, current_pid=1)
    assert discovery["ok"] is False
    assert discovery["error_code"] == "discovery_duplicate_process_id"
    owners = duplicate_canonical_runtime_owners(repo_root=repo, current_pid=1)
    assert owners["ok"] is False


def test_windows_discovery_command_enumerates_supported_interpreters():
    script = runtime_launcher._windows_discovery_command()
    assert "pythonw?" in script or "pythonw" in script.lower()
    assert "name='python.exe'" not in script
    assert "Where-Object" in script
    assert runtime_launcher.DISCOVERY_EXPECTED_PID_ENV in script
