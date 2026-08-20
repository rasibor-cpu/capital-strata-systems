import os
import re
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
    canonical_process_pid,
    canonical_process_pid_error,
)
from backend.certification.ov002_persistence import PersistenceError, strict_json_loads
from backend.monitoring.css_alert_models import AlertSeverity
from launcher.css_service_manager import CSSServiceManager
from launcher.css_launcher_config import LauncherConfig

# Consolidation discovery v2: Unit B strict classification + OV002 anchor semantics.
# HARD RULE: never exclude owners via os.getppid() PID-only skip.
DISCOVERY_SCHEMA = "css.runtime.process_discovery.consolidation.v2"
DISCOVERY_EXPECTED_PID_ENV = "CSS_DISCOVERY_EXPECTED_PID"
CANONICAL_LAUNCHER_MODULE = "launcher.css_runtime_launcher"
CANONICAL_MOBILE_MODULE = "launcher.css_mobile_launcher"
CANONICAL_LAUNCHER_SCRIPT_SUFFIX = os.path.normcase(
    os.path.join("launcher", "css_runtime_launcher.py")
)
CANONICAL_DASHBOARD_SCRIPT_SUFFIX = os.path.normcase(
    os.path.join("scripts", "css_live_dashboard.py")
)
CANONICAL_MOBILE_SCRIPT_SUFFIX = os.path.normcase(
    os.path.join("launcher", "css_mobile_launcher.py")
)
_PYTHON_INTERPRETER_NAMES = {
    "python",
    "python.exe",
    "pythonw",
    "pythonw.exe",
}


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0


def _discovery_failure(error_code: str, error_type: str) -> dict[str, Any]:
    return {
        "ok": False,
        "schema_version": DISCOVERY_SCHEMA,
        "processes": [],
        "anchor_pid": None,
        "self_observed": False,
        "expected_pid": None,
        "error_code": error_code,
        "error_type": error_type,
    }


def _discovery_success(
    processes: list[dict[str, Any]],
    *,
    expected_pid: int,
    anchor_pid: int,
) -> dict[str, Any]:
    return {
        "ok": True,
        "schema_version": DISCOVERY_SCHEMA,
        "processes": processes,
        "anchor_pid": anchor_pid,
        "self_observed": True,
        "expected_pid": expected_pid,
        "error_code": None,
        "error_type": None,
    }


def _tokenize_command(command_line: str) -> list[str]:
    return os.path.normcase(command_line).replace('"', " ").replace("'", " ").split()


def _interpreter_basename(token: str) -> str:
    return os.path.basename(token.rstrip("\\/"))


def _is_python_interpreter_token(token: str) -> bool:
    base = _interpreter_basename(token)
    if base in _PYTHON_INTERPRETER_NAMES:
        return True
    # Versioned interpreters only (python3, python3.12, python3.12.exe, pythonw3).
    return re.fullmatch(r"pythonw?\d+(?:\.\d+)*(\.exe)?", base) is not None


def _is_python_inline_invocation(args_after_interpreter: list[str]) -> bool:
    """Return True only for ``python [options] -c ...`` interpreter mode."""
    index = 0
    while index < len(args_after_interpreter):
        arg = args_after_interpreter[index]
        if arg == "-c":
            return True
        if arg == "-m":
            return False
        if arg.startswith("-"):
            # Interpreter option (e.g. -u, -O, -X...). Values for options that
            # take arguments are uncommon before -c/-m/script; keep scanning.
            index += 1
            continue
        # First non-option token is a script path — not inline -c mode.
        return False
    return False


def _path_has_canonical_suffix(token: str, suffix_norm: str) -> bool:
    """Exact path-suffix match using path separators (not arbitrary endswith)."""
    if not token or token.startswith("-") or "=" in token:
        return False
    normalized = os.path.normcase(token.replace("/", os.sep).replace("\\", os.sep))
    if normalized == suffix_norm:
        return True
    return normalized.endswith(os.sep + suffix_norm)


def _classify_python_invocation(args_after_interpreter: list[str]) -> str | None:
    if _is_python_inline_invocation(args_after_interpreter):
        return None

    index = 0
    while index < len(args_after_interpreter):
        arg = args_after_interpreter[index]
        if arg == "-m":
            if index + 1 >= len(args_after_interpreter):
                return None
            module = args_after_interpreter[index + 1]
            if module == CANONICAL_LAUNCHER_MODULE:
                return "canonical_launcher"
            if module == CANONICAL_MOBILE_MODULE:
                return "managed_child"
            return None
        if arg.startswith("-"):
            index += 1
            continue
        if _path_has_canonical_suffix(arg, CANONICAL_LAUNCHER_SCRIPT_SUFFIX):
            return "canonical_launcher"
        if _path_has_canonical_suffix(arg, CANONICAL_DASHBOARD_SCRIPT_SUFFIX):
            return "managed_child"
        if _path_has_canonical_suffix(arg, CANONICAL_MOBILE_SCRIPT_SUFFIX):
            return "managed_child"
        # First non-option argument is some other script — not canonical.
        return None
    return None


def classify_canonical_process_command(command_line: str) -> str | None:
    """Classify a process command line as canonical_launcher, managed_child, or None.

    Non-Python wrappers (cmd, PowerShell, explorers, etc.) never become owners
    merely because a marker string appears in their command text. Only a Python
    interpreter invocation in supported -m / script forms qualifies.
    """
    tokens = _tokenize_command(command_line)
    for index, token in enumerate(tokens):
        if not _is_python_interpreter_token(token):
            continue
        return _classify_python_invocation(tokens[index + 1 :])
    return None


def is_proven_non_owner_wrapper(command_line: str) -> bool:
    """True when the process is positively identified as a non-owner wrapper.

    Used for explicit shim classification evidence. Wrappers are never treated
    as canonical owners by classify_canonical_process_command either.
    """
    tokens = _tokenize_command(command_line)
    if not tokens:
        return False
    base = _interpreter_basename(tokens[0])
    wrapper_names = {
        "cmd.exe",
        "cmd",
        "powershell.exe",
        "powershell",
        "pwsh.exe",
        "pwsh",
        "explorer.exe",
        "explorer",
        "conhost.exe",
        "conhost",
    }
    if base not in wrapper_names:
        return False
    return classify_canonical_process_command(command_line) is None


def _windows_discovery_command() -> str:
    # Always emit a JSON object envelope so empty process sets remain parseable
    # (PowerShell ConvertTo-Json of @() alone can yield empty stdout).
    # EXPECTED_PID is supplied only via process env (never shell-interpolated).
    # Enumerate interpreter names consistent with classify_canonical_process_command:
    # python.exe, pythonw.exe, and versioned python/pythonw forms (python3.12.exe, etc.).
    return (
        f"$ExpectedPid = [int]$env:{DISCOVERY_EXPECTED_PID_ENV}; "
        "$self = Get-CimInstance Win32_Process -Filter \"ProcessId=$ExpectedPid\" "
        "-ErrorAction SilentlyContinue; "
        "$anchor = $ExpectedPid; $selfObserved = $false; "
        "if ($null -ne $self) { $anchor = [int]$self.ProcessId; $selfObserved = $true }; "
        "$namePattern = '^(?i)pythonw?(\\d+(\\.\\d+)*)?\\.exe$'; "
        "$procs = @(Get-CimInstance Win32_Process -ErrorAction Stop | "
        "Where-Object { $_.Name -match $namePattern } | "
        "Select-Object ProcessId,ParentProcessId,CommandLine); "
        f"[pscustomobject]@{{ schema_version = '{DISCOVERY_SCHEMA}'; ok = $true; "
        "anchor_pid = $anchor; self_observed = $selfObserved; processes = $procs; "
        "error_code = $null; error_type = $null } | "
        "ConvertTo-Json -Compress -Depth 4"
    )


def _parse_windows_discovery_payload(
    parsed: Any,
    *,
    expected_pid: int,
) -> tuple[list[dict[str, Any]] | None, int | None, str | None]:
    if not isinstance(parsed, dict):
        return None, None, "discovery_envelope_malformed"
    if parsed.get("schema_version") != DISCOVERY_SCHEMA:
        return None, None, "discovery_schema_mismatch"
    if parsed.get("ok") is not True:
        return None, None, "discovery_reported_failure"
    if parsed.get("error_code") not in (None, "") or parsed.get("error_type") not in (
        None,
        "",
    ):
        return None, None, "discovery_success_error_fields_present"
    anchor_pid = canonical_process_pid(parsed.get("anchor_pid"))
    if anchor_pid is None:
        return None, None, "discovery_anchor_malformed"
    if anchor_pid != expected_pid:
        return None, None, "discovery_anchor_mismatch"
    if parsed.get("self_observed") is not True:
        return None, None, "discovery_self_missing"
    processes = parsed.get("processes")
    if processes is None:
        processes = []
    if isinstance(processes, dict):
        processes = [processes]
    if not isinstance(processes, list):
        return None, None, "discovery_output_malformed"
    return processes, anchor_pid, None


def discover_canonical_runtime_processes(
    *,
    repo_root: str = REPO_ROOT,
    current_pid: int | None = None,
) -> dict[str, Any]:
    """Discover canonical CSS runtime processes with fail-closed anchor semantics.

    Returns a structured envelope:
      ok=True  → self_observed + matching anchor_pid; processes may be empty
                 (SUCCESS_WITH_ZERO_OTHER_OWNERS)
      ok=False → discovery failed / unanchored; processes is always []

    HARD RULE: never skip owners solely because pid == os.getppid().
    """
    current_pid_raw = os.getpid() if current_pid is None else current_pid
    expected_pid = canonical_process_pid(current_pid_raw)
    if expected_pid is None:
        return _discovery_failure("discovery_current_pid_malformed", "malformed_input")

    repo_norm = os.path.normcase(os.path.abspath(repo_root))
    anchor_pid: int | None = None

    try:
        if os.name == "nt":
            discovery_env = os.environ.copy()
            # Explicit validated PID only — ignore any hostile inherited value.
            discovery_env[DISCOVERY_EXPECTED_PID_ENV] = str(expected_pid)
            completed = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    _windows_discovery_command(),
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
                return _discovery_failure("discovery_empty_output", "empty_output")
            try:
                parsed = strict_json_loads(raw, source="runtime_process_discovery")
            except PersistenceError:
                return _discovery_failure("discovery_output_unreadable", "json_error")
            process_rows, anchor_pid, payload_error = _parse_windows_discovery_payload(
                parsed,
                expected_pid=expected_pid,
            )
            if payload_error:
                return _discovery_failure(payload_error, "malformed_envelope")
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
            process_rows = []
            for line in (completed.stdout or "").splitlines():
                parts = line.strip().split(None, 2)
                if len(parts) != 3:
                    if line.strip():
                        return _discovery_failure(
                            "discovery_row_malformed", "malformed_process_row"
                        )
                    continue
                try:
                    process_id = int(parts[0])
                    parent_id = int(parts[1])
                except ValueError:
                    return _discovery_failure(
                        "discovery_pid_malformed", "malformed_process_row"
                    )
                process_rows.append(
                    {
                        "ProcessId": process_id,
                        "ParentProcessId": parent_id,
                        "CommandLine": parts[2],
                    }
                )
            self_seen = any(
                canonical_process_pid(row.get("ProcessId")) == expected_pid
                for row in process_rows
            )
            if not self_seen:
                return _discovery_failure(
                    "discovery_self_missing", "unanchored_enumeration"
                )
            anchor_pid = expected_pid
    except Exception:
        return _discovery_failure("discovery_enumeration_exception", "subprocess_error")

    if anchor_pid is None or anchor_pid != expected_pid:
        return _discovery_failure("discovery_anchor_mismatch", "malformed_envelope")

    rows: list[dict[str, Any]] = []
    seen_pids: set[int] = set()
    observed_pids: set[int] = set()

    for row in process_rows or []:
        if not isinstance(row, dict):
            return _discovery_failure("discovery_row_malformed", "malformed_process_row")
        pid = canonical_process_pid(row.get("ProcessId"))
        if pid is None:
            # Accept plain JSON ints only; also tolerate numeric strings from ps.
            try:
                pid_candidate = int(row.get("ProcessId") or row.get("PID") or 0)
            except (TypeError, ValueError):
                return _discovery_failure("discovery_pid_malformed", "malformed_process_row")
            pid = canonical_process_pid(pid_candidate)
            if pid is None:
                return _discovery_failure("discovery_pid_malformed", "malformed_process_row")
        if pid in seen_pids:
            return _discovery_failure(
                "discovery_duplicate_process_id", "contradictory_ownership"
            )
        seen_pids.add(pid)
        observed_pids.add(pid)
        if pid == expected_pid:
            # Self is used for anchoring only; never reported as an owner of itself.
            continue

        # Do NOT skip pid == os.getppid() — parent canonical owners must remain visible.

        cmd = row.get("CommandLine") or row.get("COMMAND")
        if not isinstance(cmd, str) or not cmd.strip():
            # Windows often returns null CommandLine under ACL denial. Such rows
            # cannot be classified as owners and are skipped (not counted).
            # Envelope/subprocess failures still fail closed above.
            continue

        cmd_norm = os.path.normcase(cmd)
        if repo_norm not in cmd_norm:
            continue

        role = classify_canonical_process_command(cmd)
        if not role:
            continue

        parent_raw = row.get("ParentProcessId")
        parent_pid: Any = parent_raw
        if canonical_process_pid_error(parent_raw) is None:
            parent_pid = int(parent_raw)
        else:
            try:
                parent_pid = int(parent_raw) if parent_raw is not None else None
            except (TypeError, ValueError):
                parent_pid = parent_raw

        rows.append(
            {
                "pid": pid,
                "parent_pid": parent_pid,
                "role": role,
                "command_line": cmd[:500],
            }
        )

    # Envelope already required self_observed; also require anchor identity match.
    self_observed = expected_pid in observed_pids or anchor_pid == expected_pid
    if not self_observed:
        return _discovery_failure("discovery_self_missing", "unanchored_enumeration")

    return _discovery_success(
        rows,
        expected_pid=expected_pid,
        anchor_pid=anchor_pid,
    )


def duplicate_canonical_runtime_owners(
    *,
    repo_root: str = REPO_ROOT,
    current_pid: int | None = None,
) -> dict[str, Any]:
    """Return fail-closed owner discovery for canonical launchers only."""
    discovery = discover_canonical_runtime_processes(
        repo_root=repo_root,
        current_pid=current_pid,
    )
    if not discovery.get("ok"):
        return {
            "ok": False,
            "owners": [],
            "self_observed": bool(discovery.get("self_observed")),
            "anchor_pid": discovery.get("anchor_pid"),
            "expected_pid": discovery.get("expected_pid"),
            "error_code": discovery.get("error_code"),
            "error_type": discovery.get("error_type"),
        }
    owners = [
        row
        for row in discovery.get("processes") or []
        if row.get("role") == "canonical_launcher"
    ]
    return {
        "ok": True,
        "owners": owners,
        "self_observed": True,
        "anchor_pid": discovery.get("anchor_pid"),
        "expected_pid": discovery.get("expected_pid"),
        "error_code": None,
        "error_type": None,
    }


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

    owner_discovery = duplicate_canonical_runtime_owners()
    if not owner_discovery.get("ok"):
        print("Canonical Runtime Owner FAIL")
        print(
            "ERROR: Canonical runtime discovery failed "
            f"(error_code={owner_discovery.get('error_code')}, "
            f"error_type={owner_discovery.get('error_type')})."
        )
        checks_ok = False
    elif owner_discovery.get("owners"):
        print("Canonical Runtime Owner FAIL")
        for owner in owner_discovery["owners"]:
            print(
                "ERROR: Existing canonical launcher detected "
                f"(pid={owner.get('pid')})."
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


def _live_process_fields(pid: int | None, *, role: str) -> dict[str, Any]:
    if pid is None:
        raise RuntimeError(f"process_identity_pid_missing:{role}")
    live = default_identity_probe(int(pid))
    if not isinstance(live, dict):
        raise RuntimeError(f"process_identity_unavailable:{role}")
    required = (
        "parent_pid",
        "creation_time",
        "executable_path",
        "executable_sha256",
        "command_line",
    )
    missing = [field for field in required if live.get(field) in (None, "")]
    if missing:
        raise RuntimeError(
            f"process_identity_live_fields_missing:{role}:{','.join(missing)}"
        )
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


def _record_strong_process_tree(
    supervisor: CSSRuntimeSupervisor, services: list[CSSServiceManager]
) -> None:
    current = _live_process_fields(os.getpid(), role="launcher")
    supervisor.record_process_tree(
        managed_services={
            svc.service_name: _service_identity_info(svc) for svc in services
        },
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
                    t = threading.Thread(
                        target=output_stream_reader,
                        args=(svc.process.stdout, svc.service_name),
                        daemon=True,
                    )
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
