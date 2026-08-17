import os
import sys
import time
import socket
import threading
import json
import subprocess
from typing import Any, List

# Ensure repository root is in PYTHONPATH
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backend.runtime.live_environment_loader import load_css_runtime_environment

CSS_ENVIRONMENT_LOAD_TRACE = load_css_runtime_environment(REPO_ROOT)

from backend.runtime.css_runtime_supervisor import CSSRuntimeSupervisor
from backend.certification.ov002_continuity import default_identity_probe
from backend.certification.ov002_continuity import (
    canonical_process_creation_time,
    canonical_process_pid,
    canonical_process_pid_error,
)
from backend.certification.ov002_persistence import PersistenceError, strict_json_loads
from backend.monitoring.css_alert_models import AlertSeverity
from launcher.css_service_manager import CSSServiceManager
from launcher.css_launcher_config import LauncherConfig

CANONICAL_LAUNCHER_MARKERS = (
    "launcher.css_runtime_launcher",
    "launcher\\css_runtime_launcher.py",
    "launcher/css_runtime_launcher.py",
)
CANONICAL_CHILD_MARKERS = (
    "scripts\\css_live_dashboard.py",
    "scripts/css_live_dashboard.py",
    "launcher.css_mobile_launcher",
    "launcher\\css_mobile_launcher.py",
    "launcher/css_mobile_launcher.py",
)
DISCOVERY_SCHEMA = "css.runtime.process_discovery.v1"


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0


WINDOWS_DISCOVERY_SCRIPT = (
    "$ExpectedPid = [int]$env:CSS_DISCOVERY_EXPECTED_PID; "
    "$self = Get-CimInstance Win32_Process -Filter \"ProcessId=$ExpectedPid\" "
    "-ErrorAction SilentlyContinue; "
    "$anchor = $ExpectedPid; $selfObserved = $false; "
    "if ($null -ne $self) { $anchor = $self.ProcessId; $selfObserved = $true }; "
    "$procs = @(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" "
    "-ErrorAction SilentlyContinue | "
    "Select-Object ProcessId,ParentProcessId,CreationDate,ExecutablePath,CommandLine); "
    f"[pscustomobject]@{{ schema_version = '{DISCOVERY_SCHEMA}'; ok = $true; "
    "anchor_pid = $anchor; self_observed = $selfObserved; processes = $procs; "
    "error_code = $null; error_type = $null } | "
    "ConvertTo-Json -Compress -Depth 4"
)


def _discovery_failure(error_code: str, error_type: str) -> dict[str, Any]:
    return {
        "ok": False,
        "processes": [],
        "anchor_pid": None,
        "self_observed": False,
        "error_code": error_code,
        "error_type": error_type,
    }


def _parse_discovery_payload(
    parsed: Any,
    *,
    expected_pid: int,
) -> tuple[list[Any], int | None, str | None]:
    """Split a discovery payload into process rows and an optional anchor pid."""
    if not isinstance(parsed, dict):
        return [], None, "discovery_envelope_malformed"
    allowed = {
        "schema_version",
        "ok",
        "anchor_pid",
        "self_observed",
        "processes",
        "error_code",
        "error_type",
    }
    if set(parsed) != allowed:
        return [], None, "discovery_envelope_fields_mismatch"
    if parsed.get("schema_version") != DISCOVERY_SCHEMA:
        return [], None, "discovery_schema_mismatch"
    if parsed.get("ok") is not True:
        return [], None, "discovery_reported_failure"
    if parsed.get("error_code") is not None or parsed.get("error_type") is not None:
        return [], None, "discovery_success_error_fields_present"
    anchor_raw = parsed.get("anchor_pid")
    anchor_pid = canonical_process_pid(anchor_raw)
    if anchor_pid is None:
        return [], None, "discovery_anchor_malformed"
    if anchor_pid != expected_pid:
        return [], None, "discovery_anchor_mismatch"
    if parsed.get("self_observed") is not True:
        return [], None, "discovery_self_missing"
    rows = parsed.get("processes")
    if not isinstance(rows, list):
        return [], None, "discovery_output_malformed"
    observed_rows: dict[int, tuple[Any, Any, Any, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            return [], None, "discovery_row_malformed"
        allowed_row = {"ProcessId", "ParentProcessId", "CreationDate", "ExecutablePath", "CommandLine"}
        if set(row) != allowed_row:
            return [], None, "discovery_row_fields_mismatch"
        pid = canonical_process_pid(row.get("ProcessId"))
        if pid is None:
            return [], None, "discovery_pid_malformed"
        if canonical_process_pid_error(row.get("ParentProcessId")):
            return [], None, "discovery_parent_pid_malformed"
        command = row.get("CommandLine")
        if not isinstance(command, str) or not command.strip():
            return [], None, "discovery_command_unavailable"
        for optional_text in ("CreationDate", "ExecutablePath"):
            value = row.get(optional_text)
            if not isinstance(value, str) or not value.strip():
                return [], None, "discovery_row_fields_mismatch"
        if canonical_process_creation_time(row.get("CreationDate")) is None:
            return [], None, "discovery_creation_malformed"
        row_identity = (
            row.get("ParentProcessId"),
            row.get("CreationDate"),
            os.path.normcase(os.path.abspath(row.get("ExecutablePath"))),
            row.get("CommandLine").strip(),
        )
        if pid in observed_rows:
            return [], None, "discovery_duplicate_process_id"
        observed_rows[pid] = row_identity
    return rows, anchor_pid, None


def discover_canonical_runtime_processes(
    *,
    repo_root: str = REPO_ROOT,
    current_pid: int | None = None,
) -> dict[str, Any]:
    current_pid_raw = os.getpid() if current_pid is None else current_pid
    current_pid_valid = canonical_process_pid(current_pid_raw)
    if current_pid_valid is None:
        return _discovery_failure("discovery_current_pid_malformed", "malformed_input")
    current_pid = current_pid_valid
    repo_norm = os.path.normcase(os.path.abspath(repo_root))
    rows: list[dict[str, Any]] = []

    try:
        if os.name == "nt":
            discovery_env = os.environ.copy()
            discovery_env["CSS_DISCOVERY_EXPECTED_PID"] = str(current_pid)
            completed = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    WINDOWS_DISCOVERY_SCRIPT,
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=20,
                env=discovery_env,
            )
            if completed.returncode != 0:
                return _discovery_failure("discovery_powershell_failed", "subprocess_error")
            raw = (completed.stdout or "").strip()
            if not raw:
                # Empty output is indistinguishable from a silenced enumeration failure.
                return _discovery_failure("discovery_empty_output", "empty_output")
            try:
                parsed = strict_json_loads(raw, source="runtime_process_discovery")
            except PersistenceError:
                return _discovery_failure("discovery_output_unreadable", "json_error")
        else:
            completed = subprocess.run(
                ["ps", "-eo", "pid=,ppid=,command="],
                capture_output=True,
                text=True,
                check=False,
                timeout=20,
            )
            if completed.returncode != 0:
                return _discovery_failure("discovery_ps_failed", "subprocess_error")
            if not (completed.stdout or "").strip():
                return _discovery_failure("discovery_empty_output", "empty_output")
            process_rows = []
            for line in (completed.stdout or "").splitlines():
                parts = line.strip().split(None, 2)
                if len(parts) == 3:
                    try:
                        process_id = int(parts[0])
                        parent_id = int(parts[1])
                    except ValueError:
                        return _discovery_failure("discovery_pid_malformed", "malformed_process_row")
                    process_rows.append(
                        {
                            "ProcessId": process_id,
                            "ParentProcessId": parent_id,
                            "CreationDate": None,
                            "ExecutablePath": None,
                            "CommandLine": parts[2],
                        }
                    )
            parsed = {
                "schema_version": DISCOVERY_SCHEMA,
                "ok": True,
                "anchor_pid": current_pid,
                "self_observed": any(row["ProcessId"] == current_pid for row in process_rows),
                "processes": process_rows,
                "error_code": None,
                "error_type": None,
            }
        process_rows, anchor_pid, payload_error = _parse_discovery_payload(
            parsed,
            expected_pid=current_pid,
        )
        if payload_error:
            return _discovery_failure(payload_error, "malformed_envelope")
    except Exception as exc:
        return _discovery_failure("discovery_exception", type(exc).__name__)

    observed_pids: set[int] = set()
    for row in process_rows:
        if not isinstance(row, dict):
            return _discovery_failure("discovery_row_malformed", "malformed_process_row")
        pid_value = canonical_process_pid(row.get("ProcessId"))
        if pid_value is None:
            return _discovery_failure("discovery_pid_malformed", "malformed_process_row")
        observed_pids.add(pid_value)

    self_observed = current_pid in observed_pids or (
        anchor_pid is not None and int(anchor_pid) == current_pid
    )
    if not self_observed:
        # An enumeration that cannot even see this process (or its anchor) proves
        # nothing about other canonical owners, including an empty `[]` result.
        return _discovery_failure("discovery_self_missing", "unanchored_enumeration")

    canonical_launcher_seen = False
    for row in process_rows:
        pid = canonical_process_pid(row.get("ProcessId"))
        if pid is None:
            return _discovery_failure("discovery_pid_malformed", "malformed_process_row")
        if pid == current_pid:
            continue
        cmd = row.get("CommandLine")
        if not isinstance(cmd, str):
            return _discovery_failure("discovery_command_unavailable", "partial_process_row")
        if not cmd:
            return _discovery_failure("discovery_command_unavailable", "partial_process_row")
        cmd_norm = os.path.normcase(cmd)
        if repo_norm not in cmd_norm:
            continue
        # Inline Python diagnostics/imports may mention runtime module names without
        # actually owning a CSS runtime. Classify only executable script/module tokens.
        tokens = cmd_norm.replace(chr(34), " ").replace(chr(39), " ").split()
        is_python_inline = "-c" in tokens
        matched_roles = []
        if not is_python_inline:
            if any(token == item or token.endswith(item) for token in tokens for item in CANONICAL_LAUNCHER_MARKERS):
                matched_roles.append("canonical_launcher")
            if any(token == item or token.endswith(item) for token in tokens for item in CANONICAL_CHILD_MARKERS):
                matched_roles.append("managed_child")
        if len(matched_roles) > 1:
            return _discovery_failure(
                "discovery_conflicting_role_classification",
                "contradictory_ownership",
            )
        if not matched_roles:
            continue
        marker = matched_roles[0]
        if marker == "canonical_launcher":
            if canonical_launcher_seen:
                return _discovery_failure(
                    "discovery_duplicate_canonical_identity",
                    "contradictory_ownership",
                )
            canonical_launcher_seen = True
        rows.append(
            {
                "pid": pid,
                "parent_pid": row.get("ParentProcessId"),
                "creation_time": row.get("CreationDate"),
                "executable_path": row.get("ExecutablePath"),
                "role": marker,
            }
        )
    return {
        "ok": True,
        "processes": rows,
        "anchor_pid": anchor_pid,
        "self_observed": True,
        "error_code": None,
        "error_type": None,
    }


def _live_process_fields(pid: int | None, *, role: str) -> dict[str, Any]:
    if pid is None:
        raise RuntimeError(f"process_identity_pid_missing:{role}")
    live = default_identity_probe(int(pid))
    if not isinstance(live, dict):
        raise RuntimeError(f"process_identity_unavailable:{role}")
    required = ("parent_pid", "creation_time", "executable_path", "executable_sha256", "command_line")
    missing = [field for field in required if live.get(field) in (None, "")]
    if missing:
        raise RuntimeError(f"process_identity_live_fields_missing:{role}:{','.join(missing)}")
    return {
        "parent_pid": live["parent_pid"],
        "creation_time": live["creation_time"],
        "executable_path": live["executable_path"],
        "executable_sha256": live["executable_sha256"],
        "command_line": live["command_line"],
    }


def _service_identity_info(svc: CSSServiceManager) -> dict[str, Any]:
    info = dict(svc.get_info())
    live = _live_process_fields(info.get("pid"), role=svc.service_name)
    info.update(
        {
            "parent_pid": live["parent_pid"],
            "creation_time": live["creation_time"],
            "executable_path": live["executable_path"],
            "executable_sha256": live["executable_sha256"],
            "command_line": live["command_line"],
            "service_role": svc.service_name,
            "repo_root": REPO_ROOT,
        }
    )
    return info


def _record_strong_process_tree(supervisor: CSSRuntimeSupervisor, services: list[CSSServiceManager]) -> None:
    current = _live_process_fields(os.getpid(), role="launcher")
    supervisor.record_process_tree(
        managed_services={svc.service_name: _service_identity_info(svc) for svc in services},
        launcher_parent_pid=current["parent_pid"],
        launcher_creation_time=current["creation_time"],
        launcher_executable_path=current["executable_path"],
        launcher_executable_sha256=current["executable_sha256"],
        launcher_command_line=current["command_line"],
        supervisor_parent_pid=current["parent_pid"],
        supervisor_creation_time=current["creation_time"],
        supervisor_executable_path=current["executable_path"],
        supervisor_executable_sha256=current["executable_sha256"],
        supervisor_command_line=current["command_line"],
        repo_root=REPO_ROOT,
    )


def _record_process_tree_or_fail(
    supervisor: CSSRuntimeSupervisor,
    services: list[CSSServiceManager],
) -> None:
    """Record the strong process tree, classifying failures distinctly from shutdown."""
    try:
        _record_strong_process_tree(supervisor, services)
    except Exception as exc:
        recorder = getattr(supervisor, "record_identity_verification_failure", None)
        if callable(recorder):
            try:
                recorder(
                    "strong_process_identity_unavailable",
                    detail_code=type(exc).__name__,
                )
            except Exception:
                pass
        raise


def duplicate_canonical_runtime_owners(
    *,
    repo_root: str = REPO_ROOT,
    current_pid: int | None = None,
) -> dict[str, Any]:
    discovery = discover_canonical_runtime_processes(
        repo_root=repo_root,
        current_pid=current_pid,
    )
    if not discovery.get("ok"):
        return {
            "ok": False,
            "owners": [],
            "self_observed": bool(discovery.get("self_observed")),
            "error_code": discovery.get("error_code") or "discovery_failed",
        }
    owners = [
        row
        for row in discovery.get("processes") or []
        if row.get("role") == "canonical_launcher"
    ]
    return {"ok": True, "owners": owners, "self_observed": True, "error_code": None}


def check_environment() -> bool:
    print("=== CSS ENVIRONMENT CHECK ===")

    checks_ok = True

    expected_python = os.path.join(REPO_ROOT, ".venv", "Scripts", "python.exe")
    actual_python = os.path.abspath(sys.executable)

    if os.path.exists(expected_python):
        if os.path.normcase(actual_python) == os.path.normcase(expected_python):
            print("Virtual Environment . PASS")
        else:
            print("Virtual Environment . FAIL")
            print(f"ERROR: CSS must be launched with: {expected_python}")
            print(f"ERROR: Current Python is:       {actual_python}")
            checks_ok = False
    else:
        print("Virtual Environment . FAIL")
        print(f"ERROR: Missing virtual environment Python: {expected_python}")
        checks_ok = False

    runtime_script = os.path.join(REPO_ROOT, "scripts", "css_live_dashboard.py")
    mobile_launcher = os.path.join(REPO_ROOT, "launcher", "css_mobile_launcher.py")
    required_files = [
        ("Runtime Script", runtime_script),
        ("Mobile Launcher", mobile_launcher),
    ]

    for label, file_path in required_files:
        if os.path.exists(file_path):
            print(f"{label:<20} PASS")
        else:
            print(f"{label:<20} FAIL")
            print(f"ERROR: Missing required file: {file_path}")
            checks_ok = False

    required_imports = [
        ("python-dotenv", "dotenv"),
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("jinja2", "jinja2"),
        ("pydantic", "pydantic"),
        ("requests", "requests"),
    ]

    for label, module_name in required_imports:
        try:
            __import__(module_name)
            print(f"{label:<20} PASS")
        except Exception as exc:
            print(f"{label:<20} FAIL")
            print(f"ERROR: Could not import {module_name}: {exc}")
            checks_ok = False

    if is_port_in_use(LauncherConfig.PORT):
        print(f"Port {LauncherConfig.PORT:<15} FAIL")
        print(f"ERROR: Port {LauncherConfig.PORT} is already in use.")
        checks_ok = False
    else:
        print(f"Port {LauncherConfig.PORT:<15} PASS")

    discovery = duplicate_canonical_runtime_owners()
    if not discovery.get("ok"):
        print("Canonical Runtime Owner FAIL")
        print(
            f"ERROR: Duplicate discovery failed "
            f"(code={discovery.get('error_code')})."
        )
        checks_ok = False
    elif discovery.get("owners"):
        print("Canonical Runtime Owner FAIL")
        for owner in discovery["owners"]:
            print(
                "ERROR: Existing canonical launcher detected "
                f"(pid={owner.get('pid')}, role={owner.get('role')})."
            )
        checks_ok = False
    else:
        print("Canonical Runtime Owner PASS")

    if checks_ok:
        print("ENVIRONMENT READY")
    else:
        print("ENVIRONMENT CHECK FAILED")

    print("=============================")
    return checks_ok

def output_stream_reader(stream, service_name):
    """Read output stream and print it prefixing with service name."""
    if stream:
        for line in iter(stream.readline, ''):
            if line:
                print(f"[{service_name}] {line.strip()}")
        stream.close()

def monitor_and_restart_services(
    services: List[CSSServiceManager],
    supervisor: CSSRuntimeSupervisor,
) -> None:
    """
    Monitor managed services and auto-restart failed ones.

    For each service that has exited unexpectedly:
      1. Record the failure with the supervisor.
      2. Consult supervisor.should_restart() — if limit exceeded, emit
         CRITICAL alert and skip.
      3. Compute exponential backoff delay based on the service's own
         restart_attempts counter (per-service, independent).
      4. Sleep for the backoff period.
      5. Emit a WARNING alert via supervisor.record_restart_attempt().
      6. Attempt restart via svc.try_restart().
      7. On success: call supervisor.record_restart_success().
      8. On failure: record another failure, and if limit now exceeded,
         call supervisor.record_restart_exhausted().

    Services that exited cleanly (status == STOPPED, retcode == 0) are
    not restarted — a clean exit is treated as intentional.
    """
    for svc in services:
        pid_before = svc.pid
        status = svc.check_status()

        if status != "FAILED":
            # RUNNING or clean STOPPED — nothing to do
            continue

        # ── Service has failed unexpectedly ───────────────────────────────────
        print(f"[{svc.service_name}] detected status FAILED")
        supervisor.record_failure(
            f"{svc.service_name} exited unexpectedly",
            service_name=svc.service_name,
            pid_before=pid_before,
        )
        svc.record_restart_eligibility()

        if not supervisor.should_restart():
            # Limit already exhausted — emit critical alert once per failure
            supervisor.record_restart_exhausted(svc.service_name)
            continue

        # ── Compute per-service backoff ───────────────────────────────────────
        # restart_attempts was already incremented by the previous try_restart
        # call (or is 0 if this is the first failure).  We use it as the
        # 1-indexed attempt number for the backoff formula.
        attempt = svc.restart_attempts + 1  # what this attempt will be
        delay = supervisor.compute_backoff_delay(attempt)

        # ── Announce and sleep ────────────────────────────────────────────────
        supervisor.record_restart_attempt(svc.service_name, attempt, delay)
        time.sleep(delay)

        # ── Attempt restart ───────────────────────────────────────────────────
        success = svc.try_restart(stdout_drain_callback=output_stream_reader)

        if success:
            supervisor.record_restart_success(
                svc.service_name,
                attempt,
                pid_before=pid_before,
                pid_after=svc.pid,
            )
            print(
                f"[{svc.service_name}] back online "
                f"(pid={svc.pid}, total_restarts={supervisor.restart_count})"
            )
        else:
            # Restart attempt itself failed (e.g. binary missing, OS error)
            supervisor.record_failure(
                f"{svc.service_name} restart attempt {attempt} failed"
            )
            print(f"[{svc.service_name}] restart attempt {attempt} failed")
            if not supervisor.should_restart():
                supervisor.record_restart_exhausted(svc.service_name)


def run_launcher():
    print("Starting CSS Always-On Runtime Launcher...")

    if not check_environment():
        print("Environment check failed. Aborting.")
        sys.exit(1)

    supervisor = CSSRuntimeSupervisor(trusted_root=REPO_ROOT)
    supervisor_started = False

    env = os.environ.copy()
    env["PYTHONPATH"] = REPO_ROOT

    # Create Service Managers
    runtime_cmd = [sys.executable, os.path.join(REPO_ROOT, "scripts", "css_live_dashboard.py")]
    runtime_svc = CSSServiceManager("CSS Runtime", runtime_cmd, REPO_ROOT, env)

    mobile_cmd = [sys.executable, "-m", "launcher.css_mobile_launcher"]
    mobile_svc = CSSServiceManager("Mobile Launcher", mobile_cmd, REPO_ROOT, env)

    services = [runtime_svc, mobile_svc]
    started_services: list[CSSServiceManager] = []

    try:
        supervisor.start()
        supervisor_started = True

        for svc in services:
            if svc.start():
                started_services.append(svc)
                # Start thread to drain output to prevent blocking
                if svc.process and svc.process.stdout:
                    t = threading.Thread(target=output_stream_reader, args=(svc.process.stdout, svc.service_name), daemon=True)
                    t.start()

        _record_process_tree_or_fail(supervisor, services)

        print("\nCSS Runtime ........ RUNNING")
        print("Mobile Launcher .... RUNNING")
        print("Supervisor ......... RUNNING")
        print("\nSYSTEM STATUS ...... OPERATIONAL\n")

        while True:
            time.sleep(10)
            supervisor.heartbeat()
            # Mid-run continuity: persist duplicate-owner discovery into supervisor state.
            discovery = duplicate_canonical_runtime_owners()
            if not discovery.get("ok"):
                supervisor.record_duplicate_discovery(
                    {
                        "ok": False,
                        "owners": [],
                        "error_code": discovery.get("error_code") or "discovery_failed",
                    }
                )
            else:
                filtered = [
                    owner
                    for owner in discovery.get("owners") or []
                    if int(owner.get("pid") or -1) != int(os.getpid())
                ]
                supervisor.record_duplicate_discovery(
                    {
                        "ok": True,
                        "owners": filtered,
                        "error_code": None,
                    }
                )
            _record_process_tree_or_fail(supervisor, services)
            monitor_and_restart_services(services, supervisor)
    except KeyboardInterrupt:
        print("\nShutdown requested...")
    finally:
        for svc in started_services:
            svc.stop()
        if supervisor_started:
            supervisor.stop()
        print("CSS Always-On Runtime Launcher stopped.")

if __name__ == "__main__":
    run_launcher()
