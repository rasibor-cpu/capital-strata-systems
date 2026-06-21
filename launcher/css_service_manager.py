import os
import time
import subprocess
from datetime import datetime, timezone
from typing import Dict, Any

class CSSServiceManager:
    """
    Lightweight service tracking for CSS runtime processes.
    Manages process lifecycles and records restart eligibility without automatically restarting.
    """
    def __init__(self, service_name: str, cmd: list[str], cwd: str, env: Dict[str, str] = None):
        self.service_name = service_name
        self.cmd = cmd
        self.cwd = cwd
        self.env = env or os.environ.copy()
        
        self.pid: int = None
        self.status: str = "STOPPED"
        self.started_at: str = None
        self.restart_count: int = 0
        self.process: subprocess.Popen = None

    def start(self) -> bool:
        """Starts the process if not running."""
        if self.status == "RUNNING" and self.process and self.process.poll() is None:
            return False
            
        try:
            self.status = "STARTING"
            self.process = subprocess.Popen(
                self.cmd,
                cwd=self.cwd,
                env=self.env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            self.pid = self.process.pid
            self.status = "RUNNING"
            self.started_at = datetime.now(timezone.utc).isoformat()
            return True
        except Exception as e:
            self.status = "FAILED"
            print(f"[{self.service_name}] Failed to start: {e}")
            return False

    def check_status(self) -> str:
        """Checks if process is running. Updates state if exited."""
        if self.status == "RUNNING" and self.process:
            retcode = self.process.poll()
            if retcode is not None:
                # Process exited
                self.status = "STOPPED" if retcode == 0 else "FAILED"
                self.pid = None
        return self.status

    def record_restart_eligibility(self):
        """Records that the process is eligible for a restart (used by orchestrator)."""
        self.restart_count += 1

    def stop(self) -> None:
        """Stops the process gracefully, then forcefully if needed."""
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            self.status = "STOPPED"
            self.pid = None

    def get_info(self) -> Dict[str, Any]:
        return {
            "service_name": self.service_name,
            "pid": self.pid,
            "status": self.status,
            "started_at": self.started_at,
            "restart_count": self.restart_count
        }
