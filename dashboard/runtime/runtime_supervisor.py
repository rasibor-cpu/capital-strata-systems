from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from dashboard.runtime.endurance_evidence import (
    HashChainedLedger,
    atomic_write_json,
    sha256_file,
)
from dashboard.runtime.runtime_operational_state import (
    MANUAL_INTERVENTION_REQUIRED,
    evaluate_restart_policy,
)


STATE_PATH = Path("runtime") / "css_supervisor_state.json"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
RESTART_LIMIT = 3
RESTART_WINDOW_SECONDS = 300

# Run lifecycle. A run that reached a terminal status can never be resumed or
# relaunched under the same run_id -- a new run needs a new run_id.
RUN_ACTIVE = "ACTIVE"
RUN_FAILED = "FAILED"
RUN_STOPPED = "STOPPED"
TERMINAL_RUN_STATUSES = frozenset({RUN_FAILED, RUN_STOPPED})


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def describe_exit_code(exit_code: int | None) -> dict[str, Any]:
    """Decode a child exit status so the cause is not lost (OV-002 Attempt 2
    recorded eight exits with no exit code at all)."""
    if exit_code is None:
        return {"exit_code": None, "signal": None, "description": "unknown"}
    if exit_code < 0:
        try:
            name = signal.Signals(-exit_code).name
        except ValueError:
            name = f"SIG{-exit_code}"
        return {"exit_code": exit_code, "signal": name, "description": f"terminated by {name}"}
    if exit_code > 0xFFFF:  # Windows NTSTATUS, e.g. 0xC000013A (CTRL_C_EXIT)
        return {"exit_code": exit_code, "signal": None, "description": f"NTSTATUS 0x{exit_code:08X}"}
    return {"exit_code": exit_code, "signal": None, "description": "clean exit" if exit_code == 0 else "error exit"}


class SupervisorRunRefused(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass
class SupervisorConfig:
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    state_path: Path = STATE_PATH
    poll_seconds: float = 1.0
    # Cumulative unexpected restarts allowed for the whole run. The rolling
    # window below now only paces backoff; it can no longer re-arm the limit
    # (the Attempt-2 defect: the limit gated consecutive failures, so a
    # process that crashed every few minutes was restarted indefinitely).
    max_restarts: int = RESTART_LIMIT
    restart_window_seconds: int = RESTART_WINDOW_SECONDS
    run_id: str | None = None
    evidence_dir: Path | None = None


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
        self._child_log: Any = None
        self.restart_timestamps: list[str] = []
        self.shutdown_requested = False
        self.shutdown_signal: str | None = None
        self.ledger: HashChainedLedger | None = None
        evidence = self.config.evidence_dir
        if evidence is not None:
            evidence = Path(evidence)
            evidence.mkdir(parents=True, exist_ok=True)
            self.ledger = HashChainedLedger(evidence / "supervisor_events.jsonl")
        self.state: dict[str, Any] = {
            "schema_version": "css.runtime_supervisor.v2",
            "run_id": self.config.run_id,
            "run_status": RUN_ACTIVE,
            "terminal_reason": None,
            "supervisor_pid": None,
            "child_pid": None,
            "child_generation": 0,
            "child_launched_at_utc": None,
            "started_at_utc": _utc_now(),
            "last_observed_at_utc": _utc_now(),
            "status": "UNKNOWN",
            "restart_count": 0,
            "unexpected_restart_count": 0,
            "max_restarts": self.config.max_restarts,
            "restart_window_seconds": self.config.restart_window_seconds,
            "restart_timestamps_utc": [],
            "last_restart_at_utc": None,
            "last_exit_code": None,
            "last_exit": None,
            "manual_intervention_required": False,
            "shutdown_requested": False,
            "shutdown_signal": None,
        }
        self._resume_run_state()

    # -- persistence -------------------------------------------------------
    def _resume_run_state(self) -> None:
        """Carry the run's counters across a supervisor restart. The counter
        can only grow; a terminal run can never be resumed; a run whose
        state file vanished while its ledger exists is refused."""
        run_id = self.config.run_id
        if not run_id:
            return
        path = Path(self.config.state_path)
        prior: dict[str, Any] | None = None
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict) and loaded.get("run_id") == run_id:
                    prior = loaded
            except (OSError, ValueError) as exc:
                raise SupervisorRunRefused("SUPERVISOR_STATE_UNREADABLE") from exc
        ledger_rows = self.ledger.verify() if self.ledger is not None else []
        if prior is None and ledger_rows:
            raise SupervisorRunRefused("SUPERVISOR_STATE_MISSING_FOR_EXISTING_RUN")
        if prior is None:
            return
        if prior.get("run_status") in TERMINAL_RUN_STATUSES:
            raise SupervisorRunRefused(f"RUN_ALREADY_{prior.get('run_status')}")
        # The ledger, not the editable state file, is authoritative: a state
        # file hand-edited back to ACTIVE or to a lower count cannot revive or
        # launder a run whose ledger already records the failure.
        ledger_types = [row.get("event_type") for row in ledger_rows]
        if "RUN_FAILED" in ledger_types or "SUPERVISOR_STOPPED" in ledger_types:
            raise SupervisorRunRefused("RUN_ALREADY_TERMINAL_IN_LEDGER")
        derived = {
            "unexpected_restart_count": ledger_types.count("CHILD_EXITED_UNEXPECTEDLY"),
            "restart_count": ledger_types.count("CHILD_RESTART_SCHEDULED"),
            "child_generation": ledger_types.count("CHILD_LAUNCHED"),
        }
        for key in ("restart_count", "unexpected_restart_count", "child_generation"):
            self.state[key] = max(int(prior.get(key) or 0), derived[key], int(self.state[key]))
        self.restart_timestamps = list(prior.get("restart_timestamps_utc") or [])
        self.state["restart_timestamps_utc"] = list(self.restart_timestamps)
        self.state["started_at_utc"] = prior.get("started_at_utc") or self.state["started_at_utc"]
        self._event("SUPERVISOR_RESUMED", prior_supervisor_pid=prior.get("supervisor_pid"),
                    unexpected_restart_count=self.state["unexpected_restart_count"])

    def write_state(self) -> None:
        self.state["last_observed_at_utc"] = _utc_now()
        atomic_write_json(self.config.state_path, self.state)

    def _event(self, event_type: str, **fields: Any) -> None:
        if self.ledger is not None:
            self.ledger.append(event_type, run_id=self.config.run_id, supervisor_pid=os.getpid(), **fields)

    # -- child lifecycle ---------------------------------------------------
    def _child_env(self) -> dict[str, str]:
        env = dict(os.environ)
        if self.config.evidence_dir is not None:
            evidence = Path(self.config.evidence_dir)
            env["CSS_RUNTIME_HEARTBEAT_FILE"] = str(evidence / "runtime_heartbeat.json")
            env["CSS_RUNTIME_STACK_DUMP_FILE"] = str(evidence / "runtime_stack_dumps.log")
        return env

    def launch_child(self) -> Any:
        if self.state.get("run_status") in TERMINAL_RUN_STATUSES:
            raise SupervisorRunRefused(f"RUN_ALREADY_{self.state['run_status']}")
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
        generation = int(self.state["child_generation"]) + 1
        kwargs: dict[str, Any] = {"cwd": Path.cwd()}
        log_path = None
        if self.config.evidence_dir is not None:
            log_dir = Path(self.config.evidence_dir) / "child_logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / f"generation_{generation:03d}.log"
            self._child_log = open(log_path, "a", encoding="utf-8")
            kwargs.update(
                env=self._child_env(),
                # Headless: an interactive prompt in the child fails fast and
                # visibly (EOFError in its log) instead of blocking forever.
                stdin=subprocess.DEVNULL,
                stdout=self._child_log,
                stderr=subprocess.STDOUT,
            )
        previous_pid = self.state.get("child_pid")
        self.child = self.process_factory(command, **kwargs)
        self.state["child_generation"] = generation
        self.state["child_pid"] = getattr(self.child, "pid", None)
        self.state["child_launched_at_utc"] = _utc_now()
        self.state["supervisor_pid"] = os.getpid()
        self.state["status"] = "HEALTHY"
        self._event("CHILD_LAUNCHED", generation=generation, child_pid=self.state["child_pid"],
                    previous_child_pid=previous_pid, command=command[2:],
                    child_log=str(log_path) if log_path else None)
        self.write_state()
        return self.child

    def observe_child(self) -> int | None:
        if self.child is None:
            return None
        return self.child.poll()

    def _close_child_log(self) -> str | None:
        if self._child_log is None:
            return None
        name = self._child_log.name
        self._child_log.close()
        self._child_log = None
        return sha256_file(name)

    def handle_child_exit(self, exit_code: int) -> bool:
        exit_info = {**describe_exit_code(exit_code), "observed_at_utc": _utc_now(),
                     "child_pid": self.state.get("child_pid"), "generation": self.state.get("child_generation")}
        exit_info["child_log_sha256"] = self._close_child_log()
        self.state["last_exit_code"] = exit_code
        self.state["last_exit"] = exit_info
        self.state["child_pid"] = None
        self.state["unexpected_restart_count"] += 1
        self._event("CHILD_EXITED_UNEXPECTEDLY", **exit_info)

        over_run_limit = self.state["unexpected_restart_count"] > self.config.max_restarts
        decision = evaluate_restart_policy(
            self.restart_timestamps,
            max_restarts=self.config.max_restarts,
            window_seconds=self.config.restart_window_seconds,
        )
        if over_run_limit or not decision.allowed or decision.recovery_status == MANUAL_INTERVENTION_REQUIRED:
            reason = "RESTART_LIMIT_EXCEEDED" if over_run_limit else "RESTART_LOOP_WINDOW_EXCEEDED"
            self.state["status"] = MANUAL_INTERVENTION_REQUIRED
            self.state["manual_intervention_required"] = True
            self.state["run_status"] = RUN_FAILED
            self.state["terminal_reason"] = reason
            self._event("RUN_FAILED", reason=reason, unexpected_restart_count=self.state["unexpected_restart_count"],
                        max_restarts=self.config.max_restarts)
            self.write_state()
            return False

        now = _utc_now()
        self.restart_timestamps.append(now)
        self.state["restart_timestamps_utc"] = list(self.restart_timestamps)
        self.state["restart_count"] += 1
        self.state["last_restart_at_utc"] = now
        self.state["status"] = "DEGRADED"
        self._event("CHILD_RESTART_SCHEDULED", restart_count=self.state["restart_count"],
                    max_restarts=self.config.max_restarts, backoff_seconds=decision.backoff_seconds)
        self.write_state()
        if decision.backoff_seconds:
            time.sleep(decision.backoff_seconds)
        self.launch_child()
        return True

    def request_shutdown(self, signum: Any = None, *_args: Any) -> None:
        self.shutdown_requested = True
        if isinstance(signum, int):
            try:
                self.shutdown_signal = signal.Signals(signum).name
            except ValueError:
                self.shutdown_signal = str(signum)
        self.state["shutdown_requested"] = True
        self.state["shutdown_signal"] = self.shutdown_signal

    def shutdown(self) -> None:
        exit_code = None
        if self.child is not None:
            if self.child.poll() is None:
                self.child.terminate()
                try:
                    self.child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.child.kill()
                    self.child.wait(timeout=10)
            # Recorded even when the child had already exited on its own.
            exit_code = self.child.poll()
        log_hash = self._close_child_log()
        self.state["status"] = "STOPPED"
        self.state["child_pid"] = None
        if self.state.get("run_status") == RUN_ACTIVE and self.config.run_id:
            self.state["run_status"] = RUN_STOPPED
            self.state["terminal_reason"] = (
                f"CONTROLLED_SHUTDOWN:{self.shutdown_signal}" if self.shutdown_signal else "CONTROLLED_SHUTDOWN"
            )
        self._event("SUPERVISOR_STOPPED", signal=self.shutdown_signal, child_exit=describe_exit_code(exit_code),
                    child_log_sha256=log_hash, run_status=self.state.get("run_status"))
        self.write_state()

    def run(self) -> int:
        signal.signal(signal.SIGINT, self.request_shutdown)
        signal.signal(signal.SIGTERM, self.request_shutdown)
        if hasattr(signal, "SIGBREAK"):  # pragma: no cover - Windows CTRL_BREAK from the monitor
            signal.signal(signal.SIGBREAK, self.request_shutdown)
        self._event("SUPERVISOR_STARTED", max_restarts=self.config.max_restarts, host=self.config.host,
                    port=self.config.port)
        self.launch_child()
        try:
            while not self.shutdown_requested:
                exit_code = self.observe_child()
                if exit_code is not None and not self.handle_child_exit(exit_code):
                    return 1
                if exit_code is None:
                    self.write_state()
                time.sleep(self.config.poll_seconds)
        finally:
            self.shutdown()
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CSS runtime supervisor")
    parser.add_argument("--run-id")
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--state-path", type=Path)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--max-restarts", type=int, default=RESTART_LIMIT)
    args = parser.parse_args(argv)
    state_path = args.state_path or (args.evidence_dir / "supervisor_state.json" if args.evidence_dir else STATE_PATH)
    config = SupervisorConfig(host=args.host, port=args.port, state_path=state_path, max_restarts=args.max_restarts,
                              run_id=args.run_id, evidence_dir=args.evidence_dir)
    try:
        supervisor = RuntimeSupervisor(config)
    except SupervisorRunRefused as exc:
        print(f"[SUPERVISOR] refused: {exc.code}", file=sys.stderr)
        return 2
    return supervisor.run()


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "RESTART_LIMIT",
    "RESTART_WINDOW_SECONDS",
    "RUN_ACTIVE",
    "RUN_FAILED",
    "RUN_STOPPED",
    "RuntimeSupervisor",
    "SupervisorConfig",
    "SupervisorRunRefused",
    "STATE_PATH",
    "describe_exit_code",
]
