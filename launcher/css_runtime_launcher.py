import os
import sys
import time
import socket
import threading
from typing import List

# Ensure repository root is in PYTHONPATH
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backend.runtime.css_runtime_supervisor import CSSRuntimeSupervisor
from backend.monitoring.css_alert_models import AlertSeverity
from launcher.css_service_manager import CSSServiceManager
from launcher.css_launcher_config import LauncherConfig

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

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
        status = svc.check_status()

        if status != "FAILED":
            # RUNNING or clean STOPPED — nothing to do
            continue

        # ── Service has failed unexpectedly ───────────────────────────────────
        print(f"[{svc.service_name}] detected status FAILED")
        supervisor.record_failure(f"{svc.service_name} exited unexpectedly")
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
            supervisor.record_restart_success(svc.service_name, attempt)
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
