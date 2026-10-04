"""OV-002 endurance monitor for this release line.

An independent recorder process that launches the release line's own
supervisor (``dashboard.runtime.runtime_supervisor``) and records, at a fixed
cadence, everything an endurance reviewer needs to decide whether the run was
continuous -- and invalidates the run automatically, permanently and
visibly, the moment it was not.

What it does NOT do: it never certifies anything. A run that reaches its
target ends ``COMPLETE_PENDING_GOVERNANCE_REVIEW``. It never changes trading,
broker, execution or kill-switch state; the safety posture it records is read
from the running server. Lessons from Attempts 1 and 2 are built in:

* exit codes, signals, PID transitions and child output are captured
  (Attempt 2 lost all eight exit causes);
* the restart limit is cumulative for the run and terminal (Attempt 2 had
  ``restart_count=8`` against a limit of 3);
* heartbeat loss is classified (dead / hung / blocked loop / monitor gap /
  clock / startup / shutdown) with diagnostics and a stack dump;
* commit drift and config substitution invalidate (Attempt 1);
* every artifact is in hash-chained ledgers and a SHA-256 manifest, and a
  recorder restart longer than the LOST threshold invalidates the run.
"""
from __future__ import annotations

import json
import os
import platform
import signal
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from dashboard.runtime.endurance_evidence import (
    HashChainedLedger,
    LedgerError,
    atomic_write_json,
    build_manifest,
    canonical_json,
    pid_alive,
    process_resources,
    process_state,
    read_json,
    sha256_file,
    sha256_text,
    utc_now,
)
from dashboard.runtime.heartbeat_diagnostics import (
    CLOCK_ANOMALY,
    CRITICAL_RUNTIME_LOSS,
    LOST_SECONDS,
    MONITOR_GAP,
    HeartbeatObservation,
    classify_heartbeat,
)

SCHEMA = "css.ov002_endurance.v3"
GOVERNED_TARGET_HOURS = 72.0  # docs/operations/PHASE_114D (preferred), OV-002 plan

RUNNING = "RUNNING"
INVALIDATED = "INVALIDATED"
COMPLETE = "COMPLETE_PENDING_GOVERNANCE_REVIEW"
STOPPED_BEFORE_TARGET = "STOPPED_BEFORE_TARGET"
TERMINAL = frozenset({INVALIDATED, COMPLETE, STOPPED_BEFORE_TARGET})

# Environment that must never be present in an endurance run: test/debug
# substitution or development-mode security relaxations.
FORBIDDEN_ENV = {
    "CSS_TEST_MODE": None, "CSS_AUTOMATED_INPUT": None, "PYTEST_CURRENT_TEST": None,
    "CSS_ENV": {"development", "dev", "local"},
}
# Names (never values) whose configuration is fingerprinted.
FINGERPRINT_ENV_PREFIXES = ("CSS_", "OANDA_", "COINBASE_", "QUESTRADE_", "BINANCE_", "BROKER_", "REA_")
FINGERPRINT_FILES = ("config.json", "requirements.txt", "pytest.ini")
MAX_DRIFT_SECONDS = 300  # wall vs monotonic divergence beyond this makes elapsed time unverifiable


class EnduranceRefused(RuntimeError):
    pass


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


def release_identity(repo: Path) -> dict[str, Any]:
    status = _git(repo, "status", "--porcelain", "--untracked-files=no")
    return {
        "head_sha": _git(repo, "rev-parse", "HEAD"),
        "branch": _git(repo, "rev-parse", "--abbrev-ref", "HEAD"),
        "tracked_tree_clean": status == "",
        "tracked_changes": status.splitlines()[:20],
    }


def config_fingerprint(repo: Path, env: dict[str, str] | None = None) -> dict[str, Any]:
    environ = dict(os.environ if env is None else env)
    env_part = {
        name: sha256_text(value)  # value hashed: secrets are never recorded
        for name, value in sorted(environ.items())
        if name.startswith(FINGERPRINT_ENV_PREFIXES) and not name.startswith("CSS_RUNTIME_")
    }
    files = {}
    for rel in FINGERPRINT_FILES:
        path = repo / rel
        files[rel] = sha256_file(path) if path.exists() else None
    components = {
        "env_sha256_by_name": env_part,
        "files_sha256": files,
        "python": platform.python_version(),
        "platform": platform.platform(),
    }
    return {"fingerprint": sha256_text(canonical_json(components)), "components": components}


def forbidden_env_present(env: dict[str, str] | None = None) -> list[str]:
    environ = dict(os.environ if env is None else env)
    found = []
    for name, bad_values in FORBIDDEN_ENV.items():
        value = environ.get(name)
        if value is None or value == "":
            continue
        if bad_values is None or value.strip().lower() in bad_values:
            found.append(name)
    return found


@dataclass
class MonitorConfig:
    repo: Path
    evidence_dir: Path
    run_id: str
    label: str
    target_hours: float = GOVERNED_TARGET_HOURS
    interim_checkpoint_hours: float = 23.0
    snapshot_seconds: float = 60.0
    host: str = "127.0.0.1"
    port: int = 8765
    max_restarts: int = 3


LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


class EnduranceMonitor:
    def __init__(self, config: MonitorConfig):
        # The monitor probes the supervised service over plain HTTP; it only
        # ever talks to (and the supervisor only ever binds) a loopback host.
        if config.host not in LOOPBACK_HOSTS:
            raise EnduranceRefused(f"endurance host must be loopback, got {config.host!r}")
        self.c = config
        self.dir = Path(config.evidence_dir)
        self.meta_path = self.dir / "RUN_META.json"
        self.status_path = self.dir / "RUN_STATUS.json"
        self.supervisor_state_path = self.dir / "supervisor_state.json"
        self.heartbeat_path = self.dir / "runtime_heartbeat.json"
        self.snapshots: HashChainedLedger | None = None
        self.events: HashChainedLedger | None = None
        self.supervisor: subprocess.Popen | None = None
        self.meta: dict[str, Any] = {}
        self.status: dict[str, Any] = {}
        self._stop_requested = False
        self._stop_signal: str | None = None
        # Monotonic bookkeeping (valid within one monitor process).
        self._mono_start = time.monotonic()
        self._wall_start = time.time()
        self._last_tick_mono: float | None = None
        self._last_tick_wall: float | None = None
        self._elapsed_before_resume = 0.0
        self._seen_thread = (None, None)  # (seq, monitor mono when it last advanced)
        self._seen_loop = (None, None)
        self._child_pid: int | None = None
        self._child_launch_mono: float | None = None
        self._log_offsets: dict[str, int] = {}
        self._posture_ok_mono: float | None = None
        self._last_freshness: str | None = None
        self._interim_done = False

    # -- setup ---------------------------------------------------------------
    def prepare(self) -> dict[str, Any]:
        if self.dir.exists() and any(self.dir.iterdir()):
            raise EnduranceRefused(f"evidence directory already exists: {self.dir} (a new attempt needs a new run_id)")
        forbidden = forbidden_env_present()
        if forbidden:
            raise EnduranceRefused(f"forbidden test/debug environment present: {forbidden}")
        identity = release_identity(self.c.repo)
        if not identity["tracked_tree_clean"]:
            raise EnduranceRefused(f"tracked tree is not clean at {identity['head_sha']}: {identity['tracked_changes']}")
        self.dir.mkdir(parents=True, exist_ok=True)
        fingerprint = config_fingerprint(self.c.repo)
        self.meta = {
            "schema": SCHEMA,
            "label": self.c.label,
            "run_id": self.c.run_id,
            "release": identity,
            "configuration": fingerprint,
            "target_hours": self.c.target_hours,
            "governed_target_hours": GOVERNED_TARGET_HOURS,
            "interim_checkpoint_hours": self.c.interim_checkpoint_hours,
            "interim_checkpoint_is_certifying": False,
            "snapshot_seconds": self.c.snapshot_seconds,
            "heartbeat_stale_seconds": 60,
            "heartbeat_lost_seconds": LOST_SECONDS,
            "max_restarts_for_run": self.c.max_restarts,
            "supervised_service": f"dashboard.web.web_app:app on {self.c.host}:{self.c.port} via dashboard.runtime.runtime_supervisor",
            "elapsed_carry_forward_hours": 0,
            "host": {"node": platform.node(), "system": platform.system(), "release": platform.release()},
            "monitor_pid": os.getpid(),
            "start_utc": utc_now(),
            "certification_authority": False,
        }
        atomic_write_json(self.meta_path, self.meta)
        self._open_ledgers()
        self.events.append("RUN_PREPARED", label=self.c.label, head_sha=identity["head_sha"],
                           branch=identity["branch"], config_fingerprint=fingerprint["fingerprint"],
                           target_hours=self.c.target_hours)
        self._set_status(RUNNING, reasons=[])
        return self.meta

    def _open_ledgers(self) -> None:
        self.snapshots = HashChainedLedger(self.dir / "snapshots.jsonl")
        self.events = HashChainedLedger(self.dir / "monitor_events.jsonl")

    def _set_status(self, status: str, *, reasons: list[str], **extra: Any) -> None:
        prior = self.status.get("status")
        if prior in TERMINAL and status != prior:
            return  # terminal states are monotonic
        self.status = {
            "run_id": self.c.run_id, "label": self.c.label, "status": status, "reasons": reasons,
            "updated_at_utc": utc_now(), "monitor_pid": os.getpid(),
            "supervisor_pid": getattr(self.supervisor, "pid", None) or self.status.get("supervisor_pid"),
            **extra,
        }
        atomic_write_json(self.status_path, self.status)

    def launch_supervisor(self) -> None:
        cmd = [sys.executable, "-m", "dashboard.runtime.runtime_supervisor", "--run-id", self.c.run_id,
               "--evidence-dir", str(self.dir), "--host", self.c.host, "--port", str(self.c.port),
               "--max-restarts", str(self.c.max_restarts)]
        kwargs: dict[str, Any] = {"cwd": self.c.repo, "stdin": subprocess.DEVNULL,
                                  "stdout": open(self.dir / "supervisor_console.log", "a", encoding="utf-8"),
                                  "stderr": subprocess.STDOUT}
        if os.name == "nt":  # pragma: no cover
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True  # survives a monitor crash; a resumed monitor re-attaches
        self.supervisor = subprocess.Popen(cmd, **kwargs)
        self.events.append("SUPERVISOR_LAUNCHED", supervisor_pid=self.supervisor.pid, command=cmd[1:])
        self._set_status(RUNNING, reasons=[], supervisor_pid=self.supervisor.pid)

    # -- observation ---------------------------------------------------------
    def _http_health(self) -> dict[str, Any]:
        url = f"http://{self.c.host}:{self.c.port}/health"
        started = time.monotonic()
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:  # nosec B310 - http:// + loopback host enforced in __init__
                body = json.loads(resp.read().decode("utf-8"))
                return {"status": resp.status, "latency_ms": round((time.monotonic() - started) * 1000, 1), "body": body}
        except Exception as exc:
            return {"status": None, "latency_ms": None, "error": f"{type(exc).__name__}: {str(exc)[:120]}"}

    def _scan_child_logs(self) -> dict[str, Any]:
        found = {"tracebacks": 0, "error_lines": 0, "excerpts": []}
        log_dir = self.dir / "child_logs"
        if not log_dir.exists():
            return found
        for path in sorted(log_dir.glob("*.log")):
            offset = self._log_offsets.get(path.name, 0)
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                handle.seek(offset)
                chunk = handle.read()
                self._log_offsets[path.name] = handle.tell()
            for line in chunk.splitlines():
                upper = line.upper()
                if "TRACEBACK (MOST RECENT CALL LAST)" in upper:
                    found["tracebacks"] += 1
                    found["excerpts"].append(f"{path.name}: {line[:200]}")
                elif " ERROR" in upper or "CRITICAL" in upper or upper.startswith("ERROR"):
                    found["error_lines"] += 1
                    if len(found["excerpts"]) < 10:
                        found["excerpts"].append(f"{path.name}: {line[:200]}")
        return found

    def _advance(self, seen: tuple, value: Any, now: float) -> tuple:
        if value is None:
            return seen
        if seen[0] is None or value != seen[0]:
            return (value, now)
        return seen

    def observe(self) -> dict[str, Any]:
        now_mono = time.monotonic()
        now_wall = time.time()
        monitor_gap = 0.0 if self._last_tick_mono is None else now_mono - self._last_tick_mono
        step = 0.0 if self._last_tick_wall is None else (now_wall - self._last_tick_wall) - monitor_gap
        self._last_tick_mono, self._last_tick_wall = now_mono, now_wall
        drift = (now_wall - self._wall_start) - (now_mono - self._mono_start)
        try:
            sup = read_json(self.supervisor_state_path)
        except (OSError, ValueError):
            sup = {}
        try:
            hb = read_json(self.heartbeat_path)
        except (OSError, ValueError):
            hb = {}
        child_pid = sup.get("child_pid")
        if child_pid != self._child_pid:
            if self._child_pid is not None or child_pid is not None:
                self.events.append("PID_TRANSITION", previous_child_pid=self._child_pid, child_pid=child_pid,
                                   generation=sup.get("child_generation"))
            self._child_pid = child_pid
            self._child_launch_mono = now_mono
            self._seen_thread = (None, None)
            self._seen_loop = (None, None)
        if hb.get("pid") == child_pid:
            self._seen_thread = self._advance(self._seen_thread, hb.get("thread_seq"), now_mono)
            self._seen_loop = self._advance(self._seen_loop, hb.get("loop_seq") or None, now_mono)
        thread_gap = None if self._seen_thread[1] is None else now_mono - self._seen_thread[1]
        loop_gap = None if self._seen_loop[1] is None else now_mono - self._seen_loop[1]
        alive = pid_alive(child_pid)
        classification = classify_heartbeat(HeartbeatObservation(
            monitor_gap_seconds=monitor_gap,
            seconds_since_launch=now_mono - (self._child_launch_mono or now_mono),
            thread_gap_seconds=thread_gap,
            loop_gap_seconds=loop_gap,
            pid=child_pid,
            pid_alive=alive,
            shutdown_requested=bool(sup.get("shutdown_requested")),
            wall_minus_monotonic_drift_seconds=step,
        ), expected_interval_seconds=hb.get("interval_seconds"))
        posture = hb.get("posture") if isinstance(hb.get("posture"), dict) else None
        if posture is not None and not hb.get("posture_error"):
            self._posture_ok_mono = now_mono
        identity = release_identity(self.c.repo)
        fingerprint = config_fingerprint(self.c.repo)["fingerprint"]
        elapsed_mono = now_mono - self._mono_start + self._elapsed_before_resume
        supervisor_pid = sup.get("supervisor_pid") or getattr(self.supervisor, "pid", None)
        return {
            "observed_at_utc": utc_now(),
            "elapsed_seconds_monotonic": round(elapsed_mono, 3),
            "elapsed_hours": round(elapsed_mono / 3600, 4),
            "wall_minus_monotonic_drift_seconds": round(drift, 3),
            "wall_clock_step_seconds": round(step, 3),
            "monitor_gap_seconds": round(monitor_gap, 3),
            "release": {"head_sha": identity["head_sha"], "branch": identity["branch"],
                        "tracked_tree_clean": identity["tracked_tree_clean"]},
            "config_fingerprint": fingerprint,
            "supervisor": {
                "pid": supervisor_pid, "alive": pid_alive(supervisor_pid), "status": sup.get("status"),
                "run_status": sup.get("run_status"), "terminal_reason": sup.get("terminal_reason"),
                "started_at_utc": sup.get("started_at_utc"), "restart_count": sup.get("restart_count"),
                "unexpected_restart_count": sup.get("unexpected_restart_count"),
                "restart_timestamps_utc": sup.get("restart_timestamps_utc"), "last_exit": sup.get("last_exit"),
                "child_generation": sup.get("child_generation"), "child_launched_at_utc": sup.get("child_launched_at_utc"),
                "shutdown_requested": sup.get("shutdown_requested"),
            },
            "runtime": {
                "pid": child_pid, "alive": alive, "process_state": process_state(child_pid),
                "heartbeat_started_at_utc": hb.get("started_at_utc"), "thread_seq": hb.get("thread_seq"),
                "loop_seq": hb.get("loop_seq"),
                "thread_gap_seconds": None if thread_gap is None else round(thread_gap, 3),
                "loop_gap_seconds": None if loop_gap is None else round(loop_gap, 3),
                "heartbeat": classification.as_dict(),
            },
            "resources": {"runtime": process_resources(child_pid), "supervisor": process_resources(supervisor_pid)},
            "http_health": self._http_health(),
            "safety_posture": posture,
            "safety_posture_at_utc": hb.get("posture_at_utc"),
            "safety_posture_error": hb.get("posture_error"),
            "child_log_findings": self._scan_child_logs(),
        }

    # -- rules ---------------------------------------------------------------
    def invalidation_reasons(self, snap: dict[str, Any]) -> list[str]:
        reasons = []
        sup = snap["supervisor"]
        if snap["release"]["head_sha"] != self.meta["release"]["head_sha"]:
            reasons.append("RELEASE_SHA_CHANGED")
        if not snap["release"]["tracked_tree_clean"]:
            reasons.append("RELEASE_TREE_MODIFIED")
        if snap["config_fingerprint"] != self.meta["configuration"]["fingerprint"]:
            reasons.append("CONFIGURATION_SUBSTITUTED")
        if (sup.get("unexpected_restart_count") or 0) > 0:
            reasons.append("UNEXPECTED_ENGINE_RESTART")
        if sup.get("run_status") == "FAILED":
            reasons.append(f"SUPERVISOR_RUN_FAILED:{sup.get('terminal_reason')}")
        if sup.get("run_status") == "STOPPED" and not self._stop_requested:
            reasons.append("UNEXPLAINED_SUPERVISOR_STOP")
        if not sup.get("alive") and not self._stop_requested:
            reasons.append("SUPERVISOR_PROCESS_EXITED")
        hb = snap["runtime"]["heartbeat"]
        if hb["classification"] in CRITICAL_RUNTIME_LOSS:
            reasons.append(f"CRITICAL_HEARTBEAT_LOSS:{hb['classification']}")
        if hb["classification"] == MONITOR_GAP:
            reasons.append("EVIDENCE_RECORDER_GAP")
        if abs(snap["wall_minus_monotonic_drift_seconds"]) > MAX_DRIFT_SECONDS:
            reasons.append("CLOCK_DISCONTINUITY")
        posture = snap.get("safety_posture")
        if posture:
            if posture.get("execution_allowed") is not False:
                reasons.append("UNAUTHORIZED_EXECUTION_TRANSITION:execution_allowed")
            if posture.get("live_trading_blocked") is not True:
                reasons.append("UNAUTHORIZED_EXECUTION_TRANSITION:live_trading_blocked")
            if posture.get("advisory_only") is not True:
                reasons.append("UNAUTHORIZED_EXECUTION_TRANSITION:advisory_only")
            if posture.get("broker_execution_armed") is not False:
                reasons.append("UNAUTHORIZED_EXECUTION_TRANSITION:broker_execution_armed")
            if posture.get("r7_unified_trade_gate_active") is not True:
                reasons.append("R7_TRADE_GATE_INACTIVE")
        now = time.monotonic()
        launched = self._child_launch_mono or self._mono_start
        if (self._posture_ok_mono is None and now - launched > LOST_SECONDS) or (
            self._posture_ok_mono is not None and now - self._posture_ok_mono > LOST_SECONDS
        ):
            reasons.append("SAFETY_POSTURE_UNVERIFIABLE")
        return reasons

    def _heartbeat_diagnostics(self, snap: dict[str, Any]) -> None:
        hb = snap["runtime"]["heartbeat"]
        if hb["classification"] not in CRITICAL_RUNTIME_LOSS:
            return
        pid = snap["runtime"]["pid"]
        stack_file = self.dir / "runtime_stack_dumps.log"
        before = stack_file.stat().st_size if stack_file.exists() else 0
        requested = False
        if pid and snap["runtime"]["alive"] and hasattr(signal, "SIGUSR1"):
            try:
                os.kill(int(pid), signal.SIGUSR1)
                requested = True
                time.sleep(1.0)
            except OSError:
                pass
        after = stack_file.stat().st_size if stack_file.exists() else 0
        self.events.append(
            "ENGINE_HEARTBEAT_LOST",
            classification=hb["classification"], reason=hb["reason"], gap_seconds=hb["gap_seconds"],
            expected_interval_seconds=hb["expected_interval_seconds"], lost_threshold_seconds=hb["lost_threshold_seconds"],
            last_thread_seq=snap["runtime"]["thread_seq"], last_loop_seq=snap["runtime"]["loop_seq"],
            heartbeat_started_at_utc=snap["runtime"]["heartbeat_started_at_utc"], pid=pid,
            process_state=snap["runtime"]["process_state"], stack_dump_requested=requested,
            stack_dump_bytes_added=after - before,
            restart_action="none: any unexpected restart invalidates the run",
            resulting_state=INVALIDATED,
        )

    # -- loop ----------------------------------------------------------------
    def request_stop(self, signum: Any = None, *_a: Any) -> None:
        self._stop_requested = True
        if isinstance(signum, int):
            try:
                self._stop_signal = signal.Signals(signum).name
            except ValueError:
                self._stop_signal = str(signum)

    def _stop_supervisor(self) -> None:
        pid = self.status.get("supervisor_pid")
        if not pid or not pid_alive(pid):
            return
        try:
            if os.name == "nt":  # pragma: no cover
                os.kill(int(pid), signal.CTRL_BREAK_EVENT)
            else:
                os.kill(int(pid), signal.SIGTERM)
        except OSError:
            return
        deadline = time.monotonic() + 30
        while pid_alive(pid) and time.monotonic() < deadline:
            time.sleep(0.5)
        if self.supervisor is not None:
            try:
                self.supervisor.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass

    def write_manifest(self, name: str = "MANIFEST.json") -> dict[str, Any]:
        manifest = build_manifest(self.dir, exclude=("MANIFEST.json", "MANIFEST_INTERIM.json"))
        manifest["run_id"] = self.c.run_id
        atomic_write_json(self.dir / name, manifest)
        return manifest

    def tick(self) -> str:
        snap = self.observe()
        self.snapshots.append("SNAPSHOT", **snap)
        hours = snap["elapsed_hours"]
        if snap["child_log_findings"]["tracebacks"]:
            self.events.append("UNCAUGHT_EXCEPTION_OBSERVED", count=snap["child_log_findings"]["tracebacks"],
                               excerpts=snap["child_log_findings"]["excerpts"][:5])
        freshness = (snap.get("safety_posture") or {}).get("data_freshness")
        if freshness != self._last_freshness:
            if freshness == "STALE":
                self.events.append("STALE_DATA", data_freshness=freshness)
            self._last_freshness = freshness
        if snap["runtime"]["heartbeat"]["classification"] == CLOCK_ANOMALY:
            self.events.append("CLOCK_ANOMALY", step_seconds=snap["wall_clock_step_seconds"],
                               cumulative_drift_seconds=snap["wall_minus_monotonic_drift_seconds"])
        reasons = [] if self._stop_requested else self.invalidation_reasons(snap)
        if reasons:
            self._heartbeat_diagnostics(snap)
            invalidation = {"run_id": self.c.run_id, "label": self.c.label, "reasons": reasons,
                            "observed_at_utc": snap["observed_at_utc"], "elapsed_hours": hours,
                            "elapsed_hours_credited": 0, "snapshot": snap}
            atomic_write_json(self.dir / "INVALIDATION.json", invalidation)
            self.events.append("RUN_INVALIDATED", reasons=reasons, elapsed_hours=hours)
            self._set_status(INVALIDATED, reasons=reasons, elapsed_hours=hours)
            return INVALIDATED
        if not self._interim_done and hours >= self.c.interim_checkpoint_hours:
            self._interim_done = True
            self.write_manifest("MANIFEST_INTERIM.json")
            self.events.append("INTERIM_CHECKPOINT", elapsed_hours=hours, certifying=False,
                               note="interim evidence only; governed target unchanged")
        if hours >= self.c.target_hours:
            self.events.append("TARGET_REACHED", elapsed_hours=hours, target_hours=self.c.target_hours)
            self._set_status(COMPLETE, reasons=[], elapsed_hours=hours)
            return COMPLETE
        self._set_status(RUNNING, reasons=[], elapsed_hours=hours, last_snapshot_utc=snap["observed_at_utc"],
                         supervisor_pid=snap["supervisor"].get("pid"))
        return RUNNING

    def run_loop(self) -> str:
        signal.signal(signal.SIGINT, self.request_stop)
        signal.signal(signal.SIGTERM, self.request_stop)
        if hasattr(signal, "SIGBREAK"):  # pragma: no cover - Windows `stop`
            signal.signal(signal.SIGBREAK, self.request_stop)
        outcome = RUNNING
        while outcome == RUNNING:
            outcome = self.tick()
            if outcome != RUNNING:
                break
            if self._stop_requested:
                hours = self.status.get("elapsed_hours", 0)
                self.events.append("OPERATOR_STOP", signal=self._stop_signal, elapsed_hours=hours)
                self._set_status(STOPPED_BEFORE_TARGET, reasons=[f"OPERATOR_STOP:{self._stop_signal}"], elapsed_hours=hours)
                outcome = STOPPED_BEFORE_TARGET
                break
            deadline = time.monotonic() + self.c.snapshot_seconds
            while time.monotonic() < deadline and not self._stop_requested:
                time.sleep(min(1.0, self.c.snapshot_seconds))
        self._stop_requested = True
        self._stop_supervisor()
        self.events.append("MONITOR_FINISHED", outcome=outcome)
        self.write_manifest()
        return outcome

    # -- resume after a recorder restart -------------------------------------
    @classmethod
    def resume(cls, config: MonitorConfig) -> "EnduranceMonitor":
        mon = cls(config)
        mon.meta = read_json(mon.meta_path)
        if mon.meta.get("run_id") != config.run_id:
            raise EnduranceRefused("run_id does not match the evidence directory")
        mon.status = read_json(mon.status_path)
        mon._open_ledgers()
        if mon.status.get("status") in TERMINAL:
            raise EnduranceRefused(f"run is terminal: {mon.status.get('status')}")
        rows = mon.snapshots.verify()
        last = rows[-1] if rows else None
        last_wall = datetime.fromisoformat(last["observed_at_utc"]).timestamp() if last else None
        gap = None if last_wall is None else time.time() - last_wall
        mon._elapsed_before_resume = float(last["elapsed_seconds_monotonic"]) if last else 0.0
        mon.events.append("MONITOR_RESUMED", gap_seconds=gap, prior_monitor_pid=mon.status.get("monitor_pid"))
        if gap is None or gap > LOST_SECONDS:
            reasons = ["EVIDENCE_RECORDER_GAP"]
            atomic_write_json(mon.dir / "INVALIDATION.json", {"run_id": config.run_id, "reasons": reasons,
                                                            "recorder_gap_seconds": gap, "elapsed_hours_credited": 0})
            mon.events.append("RUN_INVALIDATED", reasons=reasons, recorder_gap_seconds=gap)
            mon._set_status(INVALIDATED, reasons=reasons)
        return mon


def verify_evidence(evidence_dir: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"ledgers": {}, "manifest_problems": None}
    for name in ("snapshots.jsonl", "monitor_events.jsonl", "supervisor_events.jsonl"):
        path = evidence_dir / name
        try:
            result["ledgers"][name] = {"rows": len(HashChainedLedger(path).verify()) if path.exists() else 0, "ok": True}
        except LedgerError as exc:
            result["ledgers"][name] = {"ok": False, "error": str(exc)}
    manifest_path = evidence_dir / "MANIFEST.json"
    if manifest_path.exists():
        from dashboard.runtime.endurance_evidence import verify_manifest

        result["manifest_problems"] = verify_manifest(evidence_dir, read_json(manifest_path))
    result["ok"] = all(v.get("ok") for v in result["ledgers"].values()) and not result["manifest_problems"]
    return result


__all__ = [
    "COMPLETE", "EnduranceMonitor", "EnduranceRefused", "GOVERNED_TARGET_HOURS", "INVALIDATED", "MonitorConfig",
    "RUNNING", "STOPPED_BEFORE_TARGET", "config_fingerprint", "forbidden_env_present", "release_identity",
    "verify_evidence",
]
