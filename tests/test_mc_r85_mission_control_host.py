from __future__ import annotations

import json

from launcher import css_mission_control_host as host


def test_host_command_is_mission_control_only() -> None:
    command = host._command()
    joined = " ".join(command)
    assert host.MODULE in joined
    assert "css_runtime_launcher" not in joined
    assert "css_live_dashboard" not in joined
    assert "start_live" not in joined
    assert host.HOST == "127.0.0.1"
    assert host.PORT == 8765


def test_start_refuses_foreign_listener(monkeypatch) -> None:
    monkeypatch.setattr(host, "status", lambda: {"running": False})
    monkeypatch.setattr(host, "_port_in_use", lambda: True)
    result = host.start()
    assert result["action"] == "refused"
    assert result["reason"] == "FOREIGN_LISTENER_ON_8765"
    assert result["execution_allowed"] is False
    assert result["live_trading_blocked"] is True
    assert result["broker_execution_armed"] is False
    assert result["advisory_only"] is True
    assert result["engine_started"] is False
    assert result["questrade_activated"] is False


def test_start_records_detached_pid(monkeypatch, tmp_path) -> None:
    class _Proc:
        pid = 4242

    monkeypatch.setattr(host, "STATE_DIR", tmp_path)
    monkeypatch.setattr(host, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(host, "STDOUT_PATH", tmp_path / "stdout.log")
    monkeypatch.setattr(host, "STDERR_PATH", tmp_path / "stderr.log")
    monkeypatch.setattr(host, "status", lambda: {"running": False})
    monkeypatch.setattr(host, "_port_in_use", lambda: False)
    monkeypatch.setattr(host, "_spawn_detached", lambda: _Proc())
    monkeypatch.setattr(host, "_wait_health", lambda pid, timeout_seconds=45.0: True)
    monkeypatch.setattr(host, "_pid_alive", lambda pid: pid == 4242)
    result = host.start()
    assert result["pid"] == 4242
    assert result["action"] == "started"
    assert result["host"] == "127.0.0.1"
    assert result["port"] == 8765
    saved = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert saved["pid"] == 4242
    assert saved["execution_allowed"] is False
    assert "css_live_dashboard" not in " ".join(saved["command"])


def test_windows_flags_include_job_breakaway() -> None:
    flags = host._windows_creationflags(breakaway=True)
    assert flags & host.CREATE_BREAKAWAY_FROM_JOB
    assert flags & host.DETACHED_PROCESS
    assert flags & host.CREATE_NEW_PROCESS_GROUP
    assert flags & host.CREATE_NO_WINDOW


def test_windows_bootstrap_is_mission_control_only(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(host, "STATE_DIR", tmp_path)
    monkeypatch.setattr(host, "STDOUT_PATH", tmp_path / "stdout.log")
    monkeypatch.setattr(host, "STDERR_PATH", tmp_path / "stderr.log")
    path = host.write_windows_bootstrap()
    text = path.read_text(encoding="utf-8")
    assert "launcher.css_mobile_launcher" in text
    assert "CSS_LAUNCHER_HOST=127.0.0.1" in text
    assert "CSS_LAUNCHER_PORT=8765" in text
    assert "css_runtime_launcher" not in text
    assert "css_live_dashboard" not in text
    assert "start_live" not in text
    assert "questrade/mission-control/activate" not in text


def test_wmi_create_script_targets_win32_process() -> None:
    script = host.windows_wmi_create_script('cmd.exe /c "run_host.cmd"', r"C:\repo")
    assert "Win32_Process" in script
    assert "MethodName Create" in script
    assert "Start-Process" not in script
    assert "css_live_dashboard" not in script
