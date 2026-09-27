import pytest

import launcher.css_runtime_launcher as runtime_launcher


def _valid_identity():
    return {
        "parent_pid": 100,
        "creation_time": "2026-09-26T23:00:00+00:00",
        "executable_path": r"C:\Python\python.exe",
        "executable_sha256": "1" * 64,
        "command_line": r"C:\Python\python.exe scripts\css_live_dashboard.py",
    }


def test_transient_identity_unavailable_recovers_within_bound(monkeypatch):
    responses = iter([None, None, _valid_identity()])
    calls = []
    sleeps = []

    def probe(pid):
        calls.append(pid)
        return next(responses)

    monkeypatch.setattr(runtime_launcher, "default_identity_probe", probe)
    monkeypatch.setattr(
        runtime_launcher.time,
        "sleep",
        lambda seconds: sleeps.append(seconds),
    )

    result = runtime_launcher._live_process_fields(
        1234,
        role="CSS Runtime",
    )

    assert result["parent_pid"] == 100
    assert result["executable_sha256"] == "1" * 64
    assert calls == [1234, 1234, 1234]
    assert sleeps == [
        runtime_launcher.PROCESS_IDENTITY_PROBE_RETRY_DELAY_SECONDS,
        runtime_launcher.PROCESS_IDENTITY_PROBE_RETRY_DELAY_SECONDS,
    ]


def test_persistent_identity_unavailable_still_fails_closed(monkeypatch):
    calls = []
    sleeps = []

    def probe(pid):
        calls.append(pid)
        return None

    monkeypatch.setattr(runtime_launcher, "default_identity_probe", probe)
    monkeypatch.setattr(
        runtime_launcher.time,
        "sleep",
        lambda seconds: sleeps.append(seconds),
    )

    with pytest.raises(
        RuntimeError,
        match=r"^process_identity_unavailable:CSS Runtime$",
    ):
        runtime_launcher._live_process_fields(
            1234,
            role="CSS Runtime",
        )

    assert len(calls) == runtime_launcher.PROCESS_IDENTITY_PROBE_ATTEMPTS
    assert len(sleeps) == runtime_launcher.PROCESS_IDENTITY_PROBE_ATTEMPTS - 1


def test_incomplete_identity_fails_immediately_without_retry(monkeypatch):
    calls = []
    sleeps = []

    def probe(pid):
        calls.append(pid)
        payload = _valid_identity()
        payload["command_line"] = None
        return payload

    monkeypatch.setattr(runtime_launcher, "default_identity_probe", probe)
    monkeypatch.setattr(
        runtime_launcher.time,
        "sleep",
        lambda seconds: sleeps.append(seconds),
    )

    with pytest.raises(
        RuntimeError,
        match=r"^process_identity_live_fields_missing:CSS Runtime:command_line$",
    ):
        runtime_launcher._live_process_fields(
            1234,
            role="CSS Runtime",
        )

    assert calls == [1234]
    assert sleeps == []


def test_identity_probe_exception_remains_immediate_failure(monkeypatch):
    calls = []
    sleeps = []

    def probe(pid):
        calls.append(pid)
        raise OSError("identity provider failed")

    monkeypatch.setattr(runtime_launcher, "default_identity_probe", probe)
    monkeypatch.setattr(
        runtime_launcher.time,
        "sleep",
        lambda seconds: sleeps.append(seconds),
    )

    with pytest.raises(OSError, match="identity provider failed"):
        runtime_launcher._live_process_fields(
            1234,
            role="CSS Runtime",
        )

    assert calls == [1234]
    assert sleeps == []


def test_missing_pid_remains_immediate_failure(monkeypatch):
    calls = []

    monkeypatch.setattr(
        runtime_launcher,
        "default_identity_probe",
        lambda pid: calls.append(pid),
    )

    with pytest.raises(
        RuntimeError,
        match=r"^process_identity_pid_missing:CSS Runtime$",
    ):
        runtime_launcher._live_process_fields(
            None,
            role="CSS Runtime",
        )

    assert calls == []
