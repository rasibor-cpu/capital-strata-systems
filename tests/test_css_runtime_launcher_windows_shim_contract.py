from __future__ import annotations

import launcher.css_runtime_launcher as runtime_launcher


def test_proven_parent_interpreter_shim_is_not_duplicate(monkeypatch):
    monkeypatch.setattr(runtime_launcher.os, "name", "nt", raising=False)

    expected_pid = 2002
    shim_pid = 2001
    command = r'C:\\rasib\\source\\capital-strata-systems\\.venv\\Scripts\\python.exe C:\\rasib\\source\\capital-strata-systems\\launcher\\css_runtime_launcher.py'

    rows = [
        {
            "ProcessId": shim_pid,
            "ParentProcessId": 1500,
            "CommandLine": command,
        },
        {
            "ProcessId": expected_pid,
            "ParentProcessId": shim_pid,
            "CommandLine": command,
        },
    ]

    assert runtime_launcher._is_proven_interpreter_parent_shim(
        candidate_pid=shim_pid,
        candidate_parent_pid=1500,
        candidate_command_line=command,
        expected_pid=expected_pid,
        process_rows=rows,
    ) is True


def test_unrelated_canonical_parent_is_not_treated_as_shim(monkeypatch):
    monkeypatch.setattr(runtime_launcher.os, "name", "nt", raising=False)

    expected_pid = 3002
    candidate_pid = 3001
    candidate_command = r'C:\\rasib\\source\\capital-strata-systems\\.venv\\Scripts\\python.exe C:\\rasib\\source\\capital-strata-systems\\launcher\\css_runtime_launcher.py'
    expected_command = r'C:\\rasib\\source\\capital-strata-systems\\.venv\\Scripts\\python.exe -m launcher.css_runtime_launcher'

    rows = [
        {
            "ProcessId": candidate_pid,
            "ParentProcessId": 999,
            "CommandLine": candidate_command,
        },
        {
            "ProcessId": expected_pid,
            "ParentProcessId": 888,
            "CommandLine": expected_command,
        },
    ]

    assert runtime_launcher._is_proven_interpreter_parent_shim(
        candidate_pid=candidate_pid,
        candidate_parent_pid=999,
        candidate_command_line=candidate_command,
        expected_pid=expected_pid,
        process_rows=rows,
    ) is False
