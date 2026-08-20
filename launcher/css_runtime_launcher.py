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
from backend.monitoring.css_alert_models import AlertSeverity
from launcher.css_service_manager import CSSServiceManager
from launcher.css_launcher_config import LauncherConfig

# Consolidation discovery envelope — structured fail-closed reporting without
# adopting COW001's full OV002 EXPECTED_PID / self_observed schema wholesale.
DISCOVERY_SCHEMA = "css.runtime.process_discovery.consolidation.v1"
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
        "error_code": error_code,
        "error_type": error_type,
    }


def _discovery_success(processes: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "ok": True,
        "schema_version": DISCOVERY_SCHEMA,
        "processes": processes,
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
    return (
        "$procs = @(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" "
        "-ErrorAction Stop | Select-Object ProcessId,ParentProcessId,CommandLine); "
        f"[pscustomobject]@{{ schema_version = '{DISCOVERY_SCHEMA}'; ok = $true; "
        "processes = $procs; error_code = $null } | "
        "ConvertTo-Json -Compress -Depth 4"
    )


def _parse_windows_discovery_payload(parsed: Any) -> tuple[list[dict[str, Any]] | None, str | None]:
    if not isinstance(parsed, dict):
        return None, "discovery_envelope_malformed"
    if parsed.get("schema_version") != DISCOVERY_SCHEMA:
        return None, "discovery_schema_mismatch"
    if parsed.get("ok") is not True:
        return None, "discovery_reported_failure"
    if parsed.get("error_code") not in (None, ""):
        return None, "discovery_success_error_fields_present"
    processes = parsed.get("processes")
    if processes is None:
        processes = []
    if isinstance(processes, dict):
        processes = [processes]
    if not isinstance(processes, list):
        return None, "discovery_output_malformed"
    return processes, None


def discover_canonical_runtime_processes(
    *,
    repo_root: str = REPO_ROOT,
    current_pid: int | None = None,
) -> dict[str, Any]:
    """Discover canonical CSS runtime processes with fail-closed semantics.

    Returns a structured envelope:
      ok=True  → processes may be empty (SUCCESS_WITH_ZERO_OWNERS)
      ok=False → discovery failed / ambiguous; processes is always []
    """
    try:
        current_pid = int(current_pid if current_pid is not None else os.getpid())
    except (TypeError, ValueError):
        return _discovery_failure("discovery_current_pid_malformed", "malformed_input")

    repo_norm = os.path.normcase(os.path.abspath(repo_root))

    try:
        if os.name == "nt":
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
            )
            if completed.returncode != 0:
                return _discovery_failure("discovery_powershell_failed", "subprocess_error")
            raw = (completed.stdout or "").strip()
            if not raw:
                return _discovery_failure("discovery_empty_output", "empty_output")
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                return _discovery_failure("discovery_output_unreadable", "json_error")
            process_rows, payload_error = _parse_windows_discovery_payload(parsed)
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
                process_rows.append(
                    {
                        "ProcessId": parts[0],
                        "ParentProcessId": parts[1],
                        "CommandLine": parts[2],
                    }
                )
    except Exception:
        return _discovery_failure("discovery_enumeration_exception", "subprocess_error")

    rows: list[dict[str, Any]] = []
    seen_pids: set[int] = set()

    for row in process_rows or []:
        if not isinstance(row, dict):
            return _discovery_failure("discovery_row_malformed", "malformed_process_row")
        try:
            pid = int(row.get("ProcessId") or row.get("PID") or 0)
        except (TypeError, ValueError):
            return _discovery_failure("discovery_pid_malformed", "malformed_process_row")
        if pid <= 0:
            return _discovery_failure("discovery_pid_malformed", "malformed_process_row")
        if pid in seen_pids:
            return _discovery_failure(
                "discovery_duplicate_process_id", "contradictory_ownership"
            )
        seen_pids.add(pid)
        if pid == current_pid:
            continue

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

        rows.append(
            {
                "pid": pid,
                "parent_pid": row.get("ParentProcessId"),
                "role": role,
                "command_line": cmd[:500],
            }
        )

    return _discovery_success(rows)


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

    supervisor = CSSRuntimeSupervisor()
    supervisor.start()

    env = os.environ.copy()
    env["PYTHONPATH"] = REPO_ROOT

    # Create Service Managers
    runtime_cmd = [sys.executable, os.path.join(REPO_ROOT, "scripts", "css_live_dashboard.py")]
    runtime_svc = CSSServiceManager("CSS Runtime", runtime_cmd, REPO_ROOT, env)

    mobile_cmd = [sys.executable, "-m", "launcher.css_mobile_launcher"]
    mobile_svc = CSSServiceManager("Mobile Launcher", mobile_cmd, REPO_ROOT, env)

    services = [runtime_svc, mobile_svc]

    for svc in services:
        if svc.start():
            # Start thread to drain output to prevent blocking
            if svc.process.stdout:
                t = threading.Thread(target=output_stream_reader, args=(svc.process.stdout, svc.service_name), daemon=True)
                t.start()

    supervisor.record_process_tree(
        managed_services={svc.service_name: svc.get_info() for svc in services}
    )

    print("\nCSS Runtime ........ RUNNING")
    print("Mobile Launcher .... RUNNING")
    print("Supervisor ......... RUNNING")
    print("\nSYSTEM STATUS ...... OPERATIONAL\n")

    try:
        while True:
            time.sleep(10)
            supervisor.heartbeat()
            monitor_and_restart_services(services, supervisor)
    except KeyboardInterrupt:
        print("\nShutdown requested...")
    finally:
        for svc in services:
            svc.stop()
        supervisor.stop()
        print("CSS Always-On Runtime Launcher stopped.")

if __name__ == "__main__":
    run_launcher()
