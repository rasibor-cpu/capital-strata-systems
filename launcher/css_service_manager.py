import os
import time
import threading
import subprocess
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Callable

class CSSServiceManager:
    """
    Lightweight service tracking for CSS runtime processes.
    Manages process lifecycles, per-service restart tracking, and stdout
    stream draining.
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
        self.process: Optional[subprocess.Popen] = None

        # ── Per-service restart tracking ──────────────────────────────────────
        # restart_attempts: number of restart attempts made since the last
        # successful start (resets to 0 on a successful start).
        self.restart_attempts: int = 0
        # last_restart_at: ISO timestamp of the most recent restart attempt.
        self.last_restart_at: Optional[str] = None

    def start(self) -> bool:
        """Starts the process if not running. Resets restart_attempts on success."""
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
            self.restart_attempts = 0  # reset on successful start
            return True
        except Exception as e:
            self.status = "FAILED"
            print(f"[{self.service_name}] Failed to start: {e}")
            return False

    def try_restart(self, stdout_drain_callback: Optional[Callable] = None) -> bool:
        """
        Attempt a restart of the service.

        Increments restart_attempts and records last_restart_at.
        On success: returns True, status is RUNNING, stdout drain thread
        is launched (if stdout_drain_callback provided).
        On failure: returns False, status remains FAILED.

        Never raises — all exceptions are caught and logged.
        """
        self.restart_attempts += 1
        self.last_restart_at = datetime.now(timezone.utc).isoformat()

        try:
            # Ensure previous process resources are released
            if self.process and self.process.poll() is None:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=3)
                except Exception:
                    try:
                        self.process.kill()
                        self.process.wait()
                    except Exception:
                        pass

            success = self.start()
            if success and stdout_drain_callback and self.process and self.process.stdout:
                t = threading.Thread(
                    target=stdout_drain_callback,
                    args=(self.process.stdout, self.service_name),
                    daemon=True,
                )
                t.start()
            return success
        except Exception as e:
            self.status = "FAILED"
            print(f"[{self.service_name}] try_restart failed: {e}")
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
        """Stops the process gracefully, then forcefully if needed.

        Never reports STOPPED while the child process is still alive.
        """
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        if self.process is not None and self.process.poll() is None:
            # Fail-closed: do not claim clean stop if process remains.
            self.status = "STOP_FAILED"
            return
        self.status = "STOPPED"
        self.pid = None

    def get_info(self) -> Dict[str, Any]:
        return {
            "service_name": self.service_name,
            "pid": self.pid,
            "status": self.status,
            "started_at": self.started_at,
            "restart_count": self.restart_count,
            "restart_attempts": self.restart_attempts,
            "last_restart_at": self.last_restart_at,
        }
