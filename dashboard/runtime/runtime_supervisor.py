from __future__ import annotations

import json
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from dashboard.runtime.runtime_operational_state import (
    MANUAL_INTERVENTION_REQUIRED,
    evaluate_restart_policy,
)


STATE_PATH = Path("runtime") / "css_supervisor_state.json"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
RESTART_LIMIT = 3
RESTART_WINDOW_SECONDS = 300


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SupervisorConfig:
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    state_path: Path = STATE_PATH
    poll_seconds: float = 1.0
    max_restarts: int = RESTART_LIMIT
    restart_window_seconds: int = RESTART_WINDOW_SECONDS


class RuntimeSupervisor:
    def __init__(
        self,
        config: SupervisorConfig | None = None,
        *,
        process_factory: Callable[..., Any] = subprocess.Popen,
    ) -> None:
        self.config = config or SupervisorConfig()
        self.process_factory = process_factory
        self.child: Any = None
        self.restart_timestamps: list[str] = []
        self.shutdown_requested = False
        self.state: dict[str, Any] = {
            "schema_version": "css.runtime_supervisor.v1",
            "supervisor_pid": None,
            "child_pid": None,
            "started_at_utc": _utc_now(),
            "last_observed_at_utc": _utc_now(),
            "status": "UNKNOWN",
            "restart_count": 0,
            "unexpected_restart_count": 0,
            "restart_window_seconds": self.config.restart_window_seconds,
            "last_restart_at_utc": None,
            "last_exit_code": None,
            "manual_intervention_required": False,
        }

    def write_state(self) -> None:
        target = self.config.state_path
        target.parent.mkdir(parents=True, exist_ok=True)
        self.state["last_observed_at_utc"] = _utc_now()
        target.write_text(json.dumps(self.state, sort_keys=True), encoding="utf-8")

    def launch_child(self) -> Any:
        command = [
            sys.executable,
            "-m",
            "uvicorn",
            "dashboard.web.web_app:app",
            "--host",
            self.config.host,
            "--port",
            str(self.config.port),
        ]
        self.child = self.process_factory(command, cwd=Path.cwd())
        self.state["child_pid"] = getattr(self.child, "pid", None)
        self.state["supervisor_pid"] = __import__("os").getpid()
        self.state["status"] = "HEALTHY"
        self.write_state()
        return self.child

    def observe_child(self) -> int | None:
        if self.child is None:
            return None
        return self.child.poll()

    def handle_child_exit(self, exit_code: int) -> bool:
        self.state["last_exit_code"] = exit_code
        self.state["child_pid"] = None
        self.state["unexpected_restart_count"] += 1
        decision = evaluate_restart_policy(
            self.restart_timestamps,
            max_restarts=self.config.max_restarts,
            window_seconds=self.config.restart_window_seconds,
        )
        if not decision.allowed or decision.recovery_status == MANUAL_INTERVENTION_REQUIRED:
            self.state["status"] = MANUAL_INTERVENTION_REQUIRED
            self.state["manual_intervention_required"] = True
            self.write_state()
            return False

        now = _utc_now()
        self.restart_timestamps.append(now)
        self.state["restart_count"] += 1
        self.state["last_restart_at_utc"] = now
        self.state["status"] = "DEGRADED"
        self.write_state()
        if decision.backoff_seconds:
            time.sleep(decision.backoff_seconds)
        self.launch_child()
        return True

    def request_shutdown(self, *_args: Any) -> None:
        self.shutdown_requested = True

    def shutdown(self) -> None:
        if self.child is not None and self.child.poll() is None:
            self.child.terminate()
            try:
                self.child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.child.kill()
        self.state["status"] = "STOPPED"
        self.state["child_pid"] = None
        self.write_state()

    def run(self) -> int:
        signal.signal(signal.SIGINT, self.request_shutdown)
        signal.signal(signal.SIGTERM, self.request_shutdown)
        self.launch_child()
        try:
            while not self.shutdown_requested:
                exit_code = self.observe_child()
                if exit_code is not None and not self.handle_child_exit(exit_code):
                    return 1
                time.sleep(self.config.poll_seconds)
        finally:
            self.shutdown()
        return 0


def main() -> int:
    return RuntimeSupervisor().run()


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "RESTART_LIMIT",
    "RESTART_WINDOW_SECONDS",
    "RuntimeSupervisor",
    "SupervisorConfig",
    "STATE_PATH",
]