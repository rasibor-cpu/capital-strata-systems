import json
import math
import uuid
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from backend.monitoring.css_alert_models import AlertSeverity
from backend.monitoring.css_alert_service import CSSAlertService

BASE_RESTART_DELAY_SECONDS: float = 5.0
MAX_RESTART_DELAY_SECONDS: float = 120.0


class CSSRuntimeSupervisor:
    def __init__(
        self,
        state_dir: str = "runtime/supervisor",
        max_restart_limit: int = 3,
        alert_service: Optional[CSSAlertService] = None,
    ):
        self.supervisor_id = str(uuid.uuid4())
        self.state_dir = state_dir
        self.state_file = os.path.join(
            self.state_dir,
            "css_runtime_supervisor_state.json",
        )
        self.max_restart_limit = max_restart_limit
        self.alert_service = alert_service or CSSAlertService()

        self.started_at: Optional[str] = None
        self.stopped_at: Optional[str] = None
        self.last_heartbeat_at: Optional[str] = None
        self.failure_count: int = 0
        self.restart_count: int = 0
        self.last_failure: Optional[str] = None
        self.status: str = "STOPPED"

        self._ensure_state_dir()

    def _ensure_state_dir(self):
        os.makedirs(self.state_dir, exist_ok=True)

    def _safe_emit(
        self,
        message: str,
        severity: AlertSeverity,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        try:
            if self.alert_service:
                meta = {"supervisor_id": self.supervisor_id}
                if metadata:
                    meta.update(metadata)

                self.alert_service.emit_system_alert(
                    severity=severity,
                    message=message,
                    metadata=meta,
                    source="css_runtime_supervisor",
                )
        except Exception:
            pass

    def _persist_state(self):
        state = self.get_status()
        try:
            with open(self.state_file, "w", encoding="utf-8") as handle:
                json.dump(state, handle, indent=2)
        except Exception:
            pass

    def start(self):
        self.status = "RUNNING"
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.stopped_at = None
        self._persist_state()
        self._safe_emit("Supervisor started", AlertSeverity.INFO)

    def stop(self):
        self.status = "STOPPED"
        self.stopped_at = datetime.now(timezone.utc).isoformat()
        self._persist_state()
        self._safe_emit("Supervisor stopped", AlertSeverity.INFO)

    def heartbeat(self):
        self.last_heartbeat_at = datetime.now(timezone.utc).isoformat()
        self._persist_state()

    def check_stale_heartbeat(
        self,
        stale_threshold_seconds: int = 300,
    ) -> bool:
        if not self.last_heartbeat_at:
            return False

        last_dt = datetime.fromisoformat(self.last_heartbeat_at)
        now_dt = datetime.now(timezone.utc)

        if (now_dt - last_dt).total_seconds() > stale_threshold_seconds:
            if self.status not in ("FAILED", "DEGRADED"):
                self.record_failure("Heartbeat stale")

            self._safe_emit(
                "Heartbeat stale detected",
                AlertSeverity.CRITICAL,
            )
            return True

        return False

    def record_failure(self, reason: str):
        self.failure_count += 1
        self.last_failure = reason
        self.status = (
            "FAILED"
            if self.failure_count > self.max_restart_limit
            else "DEGRADED"
        )

        self._persist_state()

        self._safe_emit(
            f"Failure recorded: {reason}",
            AlertSeverity.WARNING,
            {
                "reason": reason,
                "failure_count": self.failure_count,
            },
        )

    def should_restart(self) -> bool:
        if self.status in ("FAILED", "DEGRADED"):
            return self.failure_count <= self.max_restart_limit
        return False

    def record_restart(self):
        self.restart_count += 1
        self.failure_count = 0
        self.last_failure = None
        self.status = "RUNNING"
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.stopped_at = None

        self._persist_state()

        self._safe_emit(
            "Restart recorded",
            AlertSeverity.INFO,
            {
                "restart_count": self.restart_count,
                "failure_count_reset": True,
            },
        )

    def compute_backoff_delay(self, attempt: int) -> float:
        if attempt < 1:
            attempt = 1

        raw = BASE_RESTART_DELAY_SECONDS * math.pow(2.0, attempt - 1)
        return min(raw, MAX_RESTART_DELAY_SECONDS)

    def record_restart_attempt(
        self,
        service_name: str,
        attempt: int,
        delay_seconds: float,
    ):
        msg = (
            f"Auto-restart attempt {attempt}/{self.max_restart_limit} "
            f"for service '{service_name}' after {delay_seconds:.1f}s backoff"
        )

        print(f"[SUPERVISOR] {msg}")

        self._safe_emit(
            msg,
            AlertSeverity.WARNING,
            {
                "service_name": service_name,
                "attempt": attempt,
                "max_restart_limit": self.max_restart_limit,
                "backoff_seconds": delay_seconds,
            },
        )

    def record_restart_success(
        self,
        service_name: str,
        attempt: int,
    ):
        msg = (
            f"Service '{service_name}' restarted successfully "
            f"(attempt {attempt})"
        )

        print(f"[SUPERVISOR] {msg}")

        self.record_restart()

        self._safe_emit(
            msg,
            AlertSeverity.INFO,
            {
                "service_name": service_name,
                "attempt": attempt,
                "total_restarts": self.restart_count,
                "failure_count": self.failure_count,
            },
        )

    def record_restart_exhausted(self, service_name: str):
        msg = (
            f"Service '{service_name}' restart limit exhausted "
            f"({self.max_restart_limit} attempts). Service will not be "
            f"restarted automatically. Manual intervention required."
        )

        print(f"[SUPERVISOR] CRITICAL: {msg}")

        self.status = "FAILED"
        self._persist_state()

        self._safe_emit(
            msg,
            AlertSeverity.CRITICAL,
            {
                "service_name": service_name,
                "max_restart_limit": self.max_restart_limit,
                "failure_count": self.failure_count,
            },
        )

    def get_status(self) -> Dict[str, Any]:
        return {
            "supervisor_id": self.supervisor_id,
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
            "last_heartbeat_at": self.last_heartbeat_at,
            "failure_count": self.failure_count,
            "restart_count": self.restart_count,
            "last_failure": self.last_failure,
            "status": self.status,
            "max_restart_limit": self.max_restart_limit,
        }
