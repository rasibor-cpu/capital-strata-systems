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
    # 1. Verify files exist
    runtime_script = os.path.join(REPO_ROOT, "scripts", "css_live_dashboard.py")
    mobile_launcher = os.path.join(REPO_ROOT, "launcher", "css_mobile_launcher.py")
    
    if not os.path.exists(runtime_script):
        print(f"ERROR: Runtime script not found: {runtime_script}")
        return False
    
    if not os.path.exists(mobile_launcher):
        print(f"ERROR: Mobile launcher not found: {mobile_launcher}")
        return False

    # 2. Verify port
    if is_port_in_use(LauncherConfig.PORT):
        print(f"ERROR: Port {LauncherConfig.PORT} is already in use.")
        return False
        
    return True

def monitor_services(services: List[CSSServiceManager], supervisor: CSSRuntimeSupervisor):
    """
    Monitor services, record failure if they exit unexpectedly.
    Only records restart eligibility, does NOT restart them yet.
    """
    for svc in services:
        status = svc.check_status()
        if status == "FAILED" or status == "STOPPED":
            print(f"[{svc.service_name}] exited with status {status}")
            supervisor.record_failure(f"{svc.service_name} exited unexpectedly")
            svc.record_restart_eligibility()
            # To prevent infinite failure recording, we don't restart. 
            # We just stop monitoring it by not doing anything further here.

def output_stream_reader(stream, service_name):
    """Read output stream and print it prefixing with service name."""
    if stream:
        for line in iter(stream.readline, ''):
            if line:
                print(f"[{service_name}] {line.strip()}")
        stream.close()

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
            monitor_services(services, supervisor)
    except KeyboardInterrupt:
        print("\nShutdown requested...")
    finally:
        for svc in services:
            svc.stop()
        supervisor.stop()
        print("CSS Always-On Runtime Launcher stopped.")

if __name__ == "__main__":
    run_launcher()
