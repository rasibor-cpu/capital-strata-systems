"""
CSS Canonical Endurance Evidence Model & Manager

Performs host reboot detection, application restart detection, and tracks
continuous operating metrics for 24h, 48h, and 72h endurance checkpoints.
"""

import time
import os
import json
import ctypes
from typing import Dict, Any, List

class CanonicalEnduranceEvidence:
    """
    State model and persistence manager for CSS long duration validation.
    """
    def __init__(self, file_path: str = "artifacts/operations/endurance_session.json"):
        self.file_path = file_path
        self.validation_start_time = time.time()
        self.validation_end_time = None
        self.elapsed_duration = 0.0
        self.uninterrupted_runtime_duration = 0.0
        self.restart_count = 0
        self.host_restart_count = 0
        self.supervisor_recovery_count = 0
        self.broker_reconnect_count = 0
        self.failed_cycle_count = 0
        self.successful_cycle_count = 0
        self.memory_baseline = 0.0
        self.memory_peak = 0.0
        self.latest_health_state = "HEALTHY"
        self.active_blockers = []
        self.warnings = []
        self.evidence_completeness = 0.0

    @staticmethod
    def get_host_boot_time() -> float:
        """Retrieves host system boot time on Windows using GetTickCount64."""
        try:
            uptime_ms = ctypes.windll.kernel32.GetTickCount64()
            return time.time() - (uptime_ms / 1000.0)
        except Exception:
            return 0.0

    def load_session(self) -> None:
        """Loads and resumes session logs from disk, detecting reboots/restarts."""
        if not os.path.exists(self.file_path):
            self.memory_baseline = self._get_approx_memory()
            self.memory_peak = self.memory_baseline
            self.save_session()
            return

        try:
            with open(self.file_path, "r") as f:
                data = json.load(f)
            
            self.validation_start_time = data.get("validation_start_time", time.time())
            self.restart_count = data.get("restart_count", 0)
            self.host_restart_count = data.get("host_restart_count", 0)
            self.supervisor_recovery_count = data.get("supervisor_recovery_count", 0)
            self.broker_reconnect_count = data.get("broker_reconnect_count", 0)
            self.failed_cycle_count = data.get("failed_cycle_count", 0)
            self.successful_cycle_count = data.get("successful_cycle_count", 0)
            self.memory_baseline = data.get("memory_baseline", self._get_approx_memory())
            self.memory_peak = data.get("memory_peak", self.memory_baseline)
            self.uninterrupted_runtime_duration = data.get("uninterrupted_runtime_duration", 0.0)

            # Detect Host Uptime or Application ID changes
            saved_pid = data.get("pid")
            saved_boot = data.get("host_boot_time", 0.0)
            current_boot = self.get_host_boot_time()

            current_pid = os.getpid()

            # Check if host rebooted (boot time changed by more than 15s)
            if saved_boot > 0.0 and current_boot > 0.0 and abs(current_boot - saved_boot) > 15.0:
                self.host_restart_count += 1
                self.uninterrupted_runtime_duration = 0.0  # Reset uninterrupted duration
                self.warnings.append("host_reboot_detected")
            # Else check if process restarted
            elif saved_pid and saved_pid != current_pid:
                self.restart_count += 1
                self.uninterrupted_runtime_duration = 0.0  # Reset uninterrupted duration
                self.warnings.append("css_process_restart_detected")

        except Exception:
            pass

    def save_session(self) -> None:
        """Saves current state to disk."""
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        payload = {
            "validation_start_time": self.validation_start_time,
            "host_boot_time": self.get_host_boot_time(),
            "pid": os.getpid(),
            "restart_count": self.restart_count,
            "host_restart_count": self.host_restart_count,
            "supervisor_recovery_count": self.supervisor_recovery_count,
            "broker_reconnect_count": self.broker_reconnect_count,
            "failed_cycle_count": self.failed_cycle_count,
            "successful_cycle_count": self.successful_cycle_count,
            "memory_baseline": self.memory_baseline,
            "memory_peak": self.memory_peak,
            "uninterrupted_runtime_duration": self.uninterrupted_runtime_duration,
            "last_heartbeat": time.time()
        }
        try:
            with open(self.file_path, "w") as f:
                json.dump(payload, f, indent=4)
        except Exception:
            pass

    def record_heartbeat(self, current_memory_mb: float = 0.0) -> None:
        """Appends active runtime ticks to uninterrupted metrics."""
        now = time.time()
        self.elapsed_duration = now - self.validation_start_time
        
        # Increment uninterrupted run duration (approx interval since start)
        self.uninterrupted_runtime_duration += 1.0
        self.successful_cycle_count += 1

        if current_memory_mb > 0.0:
            if self.memory_baseline == 0.0:
                self.memory_baseline = current_memory_mb
            self.memory_peak = max(self.memory_peak, current_memory_mb)

        self.save_session()

    def record_failure(self) -> None:
        """Records a failed loop cycle."""
        self.failed_cycle_count += 1
        self.save_session()

    def evaluate_result(self, target_hours: float = 72.0) -> Dict[str, Any]:
        """
        Runs Go/No-Go assessment on completed endurance metrics.
        """
        self.elapsed_duration = time.time() - self.validation_start_time
        target_seconds = target_hours * 3600.0

        # Calculate completeness
        self.evidence_completeness = min(100.0, (self.elapsed_duration / target_seconds) * 100.0)

        # Clear blocks and check limits
        self.active_blockers = []
        
        # 72 hours checkpoint verification
        if self.elapsed_duration < target_seconds:
            self.active_blockers.append("endurance_duration_incomplete")

        # Memory leak verification (max growth <= 150MB)
        growth = self.memory_peak - self.memory_baseline
        if growth > 150.0:
            self.active_blockers.append("excessive_memory_growth")
            self.warnings.append(f"Memory growth peaked at {growth:.1f} MB.")

        # Reconnect verification
        if self.broker_reconnect_count > 15:
            self.active_blockers.append("excessive_reconnects")

        # Result mapping
        if self.active_blockers:
            result = "FAIL"
        elif self.warnings:
            result = "CONDITIONAL PASS"
        else:
            result = "PASS"

        return {
            "result": result,
            "elapsed_duration_hours": round(self.elapsed_duration / 3600.0, 2),
            "uninterrupted_runtime_hours": round(self.uninterrupted_runtime_duration / 3600.0, 2),
            "restart_count": self.restart_count,
            "host_restart_count": self.host_restart_count,
            "broker_reconnect_count": self.broker_reconnect_count,
            "supervisor_recovery_count": self.supervisor_recovery_count,
            "memory_growth_mb": round(growth, 2),
            "evidence_completeness": round(self.evidence_completeness, 2),
            "blockers": self.active_blockers,
            "warnings": self.warnings
        }

    def _get_approx_memory(self) -> float:
        """Returns approximate process memory usage in MB using ctypes on Windows."""
        try:
            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", ctypes.c_ulong),
                    ("PageFaultCount", ctypes.c_ulong),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakWorkingSetSize", ctypes.c_size_t),
                    ("QuotaWorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolSize", ctypes.c_size_t),
                    ("QuotaPagedPoolSize", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                ]
            
            process = ctypes.windll.kernel32.GetCurrentProcess()
            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            
            if ctypes.windll.psapi.GetProcessMemoryInfo(process, ctypes.byref(counters), counters.cb):
                return counters.WorkingSetSize / (1024.0 * 1024.0)
        except Exception:
            pass
        return 50.0  # Fallback approximation
