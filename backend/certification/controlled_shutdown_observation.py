"""Controlled shutdown observation drill for OAT SHUTDOWN (OV-001 / AR-013).

Starts a short-lived supervised probe process, requests stop, and archives
PASS only when the process is gone and the bound port is released.
Never fabricates shutdown-complete while a process remains active.
"""

from __future__ import annotations

import json
import queue
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.certification.evidence_machine import REPO_ROOT, current_git_identity

DEFAULT_PORT_RELEASE_TIMEOUT_SECONDS = 10.0


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def _pick_free_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def _process_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        import os

        if os.name == "nt":
            # OpenProcess / wait — poll via tasklist is heavy; use os.kill(pid, 0) not on Windows.
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True,
                text=True,
                check=False,
            )
            return str(pid) in (result.stdout or "")
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _start_probe_readiness_monitor(
    stdout: Any,
    *,
    ready_token: str = "OV001_PROBE_READY",
) -> tuple[threading.Event, queue.Queue[str]]:
    ready = threading.Event()
    lines: queue.Queue[str] = queue.Queue()

    def _drain_stdout() -> None:
        try:
            for line in iter(stdout.readline, ""):
                text = str(line or "").strip()
                if text:
                    lines.put(text)
                if ready_token in text:
                    ready.set()
                    break
        except Exception:
            return

    threading.Thread(target=_drain_stdout, daemon=True).start()
    return ready, lines


def capture_controlled_shutdown_observation(
    output_dir: str | Path,
    *,
    port_release_timeout_seconds: float = DEFAULT_PORT_RELEASE_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """
    Run a supervised start→stop probe and return a custody-ready observation.

    ``ok`` / PASS only when:
    - stop was requested,
    - child process is not alive,
    - probe port is released within timeout,
    - final service status is STOPPED (not RUNNING).
    """
    from backend.runtime.css_runtime_supervisor import CSSRuntimeSupervisor
    from launcher.css_service_manager import CSSServiceManager

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    started = _utc_now()
    port = _pick_free_port()
    state_dir = root / "supervisor_state"
    state_dir.mkdir(parents=True, exist_ok=True)

    probe_cmd = [
        sys.executable,
        "-c",
        (
            "import socket,time;"
            f"s=socket.socket();s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);"
            f"s.bind(('127.0.0.1',{port}));s.listen(1);"
            "print('OV001_PROBE_READY',flush=True);"
            "time.sleep(3600)"
        ),
    ]

    supervisor = CSSRuntimeSupervisor(state_dir=str(state_dir))
    supervisor.start()
    supervisor_started = supervisor.status == "RUNNING" or bool(supervisor.started_at)

    env = dict(**{k: str(v) for k, v in __import__("os").environ.items()})
    env["PYTHONPATH"] = str(REPO_ROOT)
    for key in list(env):
        if key.upper().startswith("PYTEST"):
            env.pop(key, None)
    svc = CSSServiceManager(
        "OV001_ShutdownProbe",
        probe_cmd,
        str(REPO_ROOT),
        env,
    )
    start_ok = bool(svc.start())
    pid_before = svc.pid
    readiness_event: threading.Event | None = None
    readiness_lines: queue.Queue[str] | None = None
    if start_ok and svc.process and svc.process.stdout:
        readiness_event, readiness_lines = _start_probe_readiness_monitor(
            svc.process.stdout,
        )
    port_bound_before = False
    process_alive_before = False
    readiness_observed = False
    ready_deadline = time.time() + 3.0
    while time.time() < ready_deadline:
        pid_before = svc.pid
        process_alive_before = _process_alive(pid_before)
        port_bound_before = _port_in_use(port)
        readiness_observed = bool(readiness_event and readiness_event.is_set())
        if process_alive_before and port_bound_before and readiness_observed:
            break
        time.sleep(0.1)
    readiness_lines_seen: list[str] = []
    if readiness_lines is not None:
        while True:
            try:
                readiness_lines_seen.append(readiness_lines.get_nowait())
            except queue.Empty:
                break

    stop_requested_at = _utc_now()
    svc.stop()
    supervisor.stop()
    stop_acknowledged_at = _utc_now()

    deadline = time.time() + max(0.5, float(port_release_timeout_seconds))
    port_released_at: str | None = None
    while time.time() < deadline:
        if not _port_in_use(port) and not _process_alive(pid_before):
            port_released_at = _utc_now()
            break
        time.sleep(0.1)
    if port_released_at is None and not _port_in_use(port) and not _process_alive(pid_before):
        port_released_at = _utc_now()

    process_alive_after = _process_alive(pid_before)
    port_in_use_after = _port_in_use(port)
    final_status = svc.check_status()
    supervisor_final = getattr(supervisor, "status", "UNKNOWN")

    false_complete_forbidden = process_alive_after or port_in_use_after or final_status == "RUNNING"
    ok = bool(
        start_ok
        and supervisor_started
        and process_alive_before
        and port_bound_before
        and readiness_observed
        and not process_alive_after
        and not port_in_use_after
        and final_status == "STOPPED"
        and supervisor_final in {"STOPPED", "STOPPING", "STOPPED"}
        and not false_complete_forbidden
    )
    # Supervisor may report STOPPED after stop(); accept any non-RUNNING.
    if supervisor_final == "RUNNING":
        ok = False

    payload: dict[str, Any] = {
        "schema_version": "css.ov001.controlled_shutdown.v1",
        "ok": ok,
        "status": "PASS" if ok else "FAIL",
        "shutdown_performed": True,
        "shutdown_complete": ok,
        "false_complete_forbidden": True,
        "supervisor_stop_requested": True,
        "supervisor_stop_acknowledged": supervisor_final != "RUNNING",
        "supervisor_status_final": supervisor_final,
        "service_status_final": final_status,
        "probe_port": port,
        "pid_before": pid_before,
        "pid_after_cleared": svc.pid is None,
        "process_alive_before": process_alive_before,
        "readiness_observed_before_stop": readiness_observed,
        "readiness_signal": "OV001_PROBE_READY",
        "readiness_lines": readiness_lines_seen[-5:],
        "process_alive_after": process_alive_after,
        "port_bound_before": port_bound_before,
        "port_in_use_after": port_in_use_after,
        "port_released_within_timeout": port_released_at is not None and not port_in_use_after,
        "port_release_timeout_seconds": float(port_release_timeout_seconds),
        "stop_requested_at_utc": stop_requested_at,
        "stop_acknowledged_at_utc": stop_acknowledged_at,
        "port_released_at_utc": port_released_at,
        "started_at_utc": started,
        "finished_at_utc": _utc_now(),
        "execution_allowed": False,
        "advisory_only": True,
        "remediation_id": "AR-013",
        "programme": "Release Gate 3 / OV-001",
        **current_git_identity(),
    }
    if not ok:
        payload["failure_reasons"] = [
            reason
            for reason, cond in (
                ("probe_start_failed", not start_ok),
                ("supervisor_not_started", not supervisor_started),
                ("process_not_alive_before_stop", not process_alive_before),
                ("readiness_not_observed_before_stop", not readiness_observed),
                ("port_not_bound_before_stop", not port_bound_before),
                ("process_still_alive_after_stop", process_alive_after),
                ("port_still_in_use_after_stop", port_in_use_after),
                ("service_status_not_stopped", final_status != "STOPPED"),
                ("supervisor_still_running", supervisor_final == "RUNNING"),
            )
            if cond
        ]

    out = root / "SHUTDOWN_OBSERVATION.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    payload["artifact_path"] = str(out)
    return payload


def run_repeated_start_stop_cycles(
    output_dir: str | Path,
    *,
    cycles: int = 2,
) -> dict[str, Any]:
    """Verify start-stop remains reliable across repeated cycles."""
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    rows = []
    all_ok = True
    for index in range(1, max(1, cycles) + 1):
        cycle_dir = root / f"cycle_{index}"
        result = capture_controlled_shutdown_observation(cycle_dir)
        rows.append(
            {
                "cycle": index,
                "ok": result.get("ok"),
                "status": result.get("status"),
                "artifact_path": result.get("artifact_path"),
            }
        )
        if not result.get("ok"):
            all_ok = False
    summary = {
        "ok": all_ok,
        "cycles": rows,
        "cycle_count": len(rows),
        "finished_at_utc": _utc_now(),
        "execution_allowed": False,
        **current_git_identity(),
    }
    path = root / "SHUTDOWN_CYCLE_SUMMARY.json"
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    summary["artifact_path"] = str(path)
    return summary


__all__ = [
    "capture_controlled_shutdown_observation",
    "run_repeated_start_stop_cycles",
    "DEFAULT_PORT_RELEASE_TIMEOUT_SECONDS",
]
