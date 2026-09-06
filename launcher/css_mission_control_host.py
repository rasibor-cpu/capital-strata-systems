"""Mission Control-only persistent host for launcher.css_mobile_launcher.

Starts only the canonical Mission Control surface on 127.0.0.1:8765.
Does not start the trading engine, activate Questrade, or open the DPAPI store.

Windows agents that `Start-Process` uvicorn directly typically place the child
in a Job Object with KILL_ON_JOB_CLOSE. When the invoking command ends, the
child is terminated even after /health succeeded. This host detaches the child
(CREATE_BREAKAWAY_FROM_JOB / new session) and redirects logs to files.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
HOST = "127.0.0.1"
PORT = 8765
STATE_DIR = REPO_ROOT / "runtime" / "mission_control_host"
STATE_PATH = STATE_DIR / "state.json"
STDOUT_PATH = STATE_DIR / "stdout.log"
STDERR_PATH = STATE_DIR / "stderr.log"
HEALTH_URL = f"http://{HOST}:{PORT}/health"
MODULE = "launcher.css_mobile_launcher"
SAFETY = {
    "execution_allowed": False,
    "live_trading_blocked": True,
    "broker_execution_armed": False,
    "advisory_only": True,
    "engine_started": False,
    "questrade_activated": False,
    "broker_auth_attempted": False,
}

CREATE_NEW_PROCESS_GROUP = 0x00000200
DETACHED_PROCESS = 0x00000008
CREATE_NO_WINDOW = 0x08000000
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _port_in_use(host: str = HOST, port: int = PORT) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    except SystemError:
        return False
    return True


def _read_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {}
    try:
        payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_state(payload: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _command() -> list[str]:
    return [sys.executable, "-m", MODULE]


def _child_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["CSS_LAUNCHER_HOST"] = HOST
    env["CSS_LAUNCHER_PORT"] = str(PORT)
    env.setdefault("CSS_MISSION_CONTROL_HOST_ONLY", "1")
    return env


def _windows_creationflags(*, breakaway: bool) -> int:
    flags = CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS | CREATE_NO_WINDOW
    if breakaway:
        flags |= CREATE_BREAKAWAY_FROM_JOB
    return flags


def _windows_bootstrap_path() -> Path:
    return STATE_DIR / "run_host.cmd"


def write_windows_bootstrap() -> Path:
    """Write a cmd wrapper so WMI/CreateProcess can start without inheriting the agent job."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = _windows_bootstrap_path()
    lines = [
        "@echo off",
        f'set "PYTHONPATH={REPO_ROOT}"',
        f'set "CSS_LAUNCHER_HOST={HOST}"',
        f'set "CSS_LAUNCHER_PORT={PORT}"',
        'set "CSS_MISSION_CONTROL_HOST_ONLY=1"',
        f'cd /d "{REPO_ROOT}"',
        (
            f'"{sys.executable}" -m {MODULE}'
            f' >> "{STDOUT_PATH}" 2>> "{STDERR_PATH}"'
        ),
    ]
    path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
    return path


def windows_wmi_create_script(command_line: str, cwd: str) -> str:
    return (
        "$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create "
        f"-Arguments @{{ CommandLine = {json.dumps(command_line)}; "
        f"CurrentDirectory = {json.dumps(cwd)} }}; "
        "if ($r.ReturnValue -ne 0) { throw \"WMI_CREATE_FAILED:$($r.ReturnValue)\" }; "
        "Write-Output $r.ProcessId"
    )


class _ExternalPid:
    def __init__(self, pid: int) -> None:
        self.pid = int(pid)


def _spawn_windows_via_wmi() -> _ExternalPid | None:
    bootstrap = write_windows_bootstrap()
    command_line = f'cmd.exe /c "{bootstrap}"'
    script = windows_wmi_create_script(command_line, str(REPO_ROOT))
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    try:
        return _ExternalPid(int((completed.stdout or "").strip().splitlines()[-1]))
    except (ValueError, IndexError):
        return None


def _spawn_windows_createprocess() -> subprocess.Popen[Any]:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    stdout = open(STDOUT_PATH, "ab", buffering=0)
    stderr = open(STDERR_PATH, "ab", buffering=0)
    try:
        kwargs: dict[str, Any] = {
            "args": _command(),
            "cwd": str(REPO_ROOT),
            "env": _child_env(),
            "stdin": subprocess.DEVNULL,
            "stdout": stdout,
            "stderr": stderr,
            "close_fds": True,
        }
        try:
            return subprocess.Popen(creationflags=_windows_creationflags(breakaway=True), **kwargs)
        except OSError:
            # Job may forbid breakaway; still try detached flags before giving up.
            return subprocess.Popen(creationflags=_windows_creationflags(breakaway=False), **kwargs)
    finally:
        stdout.close()
        stderr.close()


def _spawn_detached() -> Any:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        wmi_child = _spawn_windows_via_wmi()
        if wmi_child is not None:
            return wmi_child
        return _spawn_windows_createprocess()
    stdout = open(STDOUT_PATH, "ab", buffering=0)
    stderr = open(STDERR_PATH, "ab", buffering=0)
    try:
        return subprocess.Popen(
            _command(),
            cwd=str(REPO_ROOT),
            env=_child_env(),
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            close_fds=True,
            start_new_session=True,
        )
    finally:
        stdout.close()
        stderr.close()


def _wait_health(pid: int, timeout_seconds: float = 45.0) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if not _pid_alive(pid):
            return False
        if _http_ok(HEALTH_URL):
            return True
        time.sleep(0.25)
    return False


def _http_ok(url: str) -> bool:
    try:
        with urlopen(url, timeout=2) as response:
            return int(response.status) == 200
    except (URLError, TimeoutError, OSError, ValueError):
        return False


def start() -> dict[str, Any]:
    existing = status()
    if existing.get("running"):
        return {**existing, "action": "already_running", **SAFETY}
    if _port_in_use() and not existing.get("running"):
        return {
            "action": "refused",
            "status": "PORT_IN_USE",
            "reason": "FOREIGN_LISTENER_ON_8765",
            "running": False,
            **SAFETY,
        }
    child = _spawn_detached()
    payload = {
        "schema": "css.mission_control_host.v1",
        "pid": child.pid,
        "host": HOST,
        "port": PORT,
        "module": MODULE,
        "command": _command(),
        "started_at": _utc_now(),
        "stdout_log": str(STDOUT_PATH),
        "stderr_log": str(STDERR_PATH),
        **SAFETY,
    }
    _write_state(payload)
    healthy = _wait_health(child.pid)
    payload["healthy"] = healthy
    payload["running"] = _pid_alive(child.pid)
    payload["action"] = "started" if payload["running"] else "exited"
    _write_state(payload)
    return payload


def status() -> dict[str, Any]:
    state = _read_state()
    pid = int(state.get("pid") or 0)
    alive = _pid_alive(pid)
    listening = _port_in_use()
    return {
        **state,
        "pid": pid or None,
        "running": alive and listening,
        "pid_alive": alive,
        "port_listening": listening,
        "same_pid_owns_port": alive and listening,
        **SAFETY,
    }


def stop() -> dict[str, Any]:
    state = status()
    pid = int(state.get("pid") or 0)
    if not pid or not _pid_alive(pid):
        return {"action": "already_stopped", "running": False, **SAFETY}
    _terminate(pid)
    deadline = time.time() + 8
    while time.time() < deadline and _pid_alive(pid):
        time.sleep(0.2)
    if _pid_alive(pid):
        _kill(pid)
    running = _pid_alive(pid)
    result = {
        "action": "stopped" if not running else "stop_failed",
        "pid": pid,
        "running": running,
        **SAFETY,
    }
    if not running:
        persisted = _read_state()
        persisted["running"] = False
        persisted["stopped_at"] = _utc_now()
        _write_state(persisted)
    return result


def _terminate(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], check=False, capture_output=True)
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass


def _kill(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], check=False, capture_output=True)
        return
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mission Control-only persistent host")
    parser.add_argument("command", choices=("start", "status", "stop"))
    args = parser.parse_args(argv)
    if args.command == "start":
        result = start()
    elif args.command == "stop":
        result = stop()
    else:
        result = status()
    print(json.dumps(result, indent=2))
    if result.get("action") in {"refused", "exited", "stop_failed"}:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
