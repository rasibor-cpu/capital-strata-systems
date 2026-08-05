import json
import math
import uuid
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from backend.monitoring.css_alert_models import AlertSeverity
from backend.monitoring.css_alert_service import CSSAlertService
from backend.monitoring.alert_bridge import CanonicalAlertBridge
from backend.certification.ov002_continuity import build_process_identity_record
from backend.certification.ov002_persistence import (
    PersistenceError,
    atomic_append_jsonl,
    atomic_write_json,
    validate_path_contained,
)

BASE_RESTART_DELAY_SECONDS: float = 5.0
MAX_RESTART_DELAY_SECONDS: float = 120.0


class CSSRuntimeSupervisor:
    def __init__(
        self,
        state_dir: str = "runtime/supervisor",
        max_restart_limit: int = 3,
        alert_service: Optional[CSSAlertService] = None,
        canonical_alert_bridge: Optional[CanonicalAlertBridge] = None,
        event_bus: Optional[Any] = None,
        failure_history_limit: int = 100,
        trusted_root: str | os.PathLike[str] | None = None,
    ):
        self.supervisor_id = str(uuid.uuid4())
        default_trusted_root = Path(__file__).resolve().parents[2]
        if trusted_root is not None:
            self.trusted_root = validate_path_contained(trusted_root, expected_root=trusted_root)
        else:
            self.trusted_root = default_trusted_root
        requested_state_dir = Path(state_dir)
        if requested_state_dir.is_absolute():
            if trusted_root is None:
                raise PersistenceError("supervisor_trusted_root_required")
            resolved_state_dir = requested_state_dir
        else:
            resolved_state_dir = self.trusted_root / requested_state_dir
        self.state_dir = str(validate_path_contained(resolved_state_dir, expected_root=self.trusted_root))
        self.state_file = os.path.join(
            self.state_dir,
            "css_runtime_supervisor_state.json",
        )
        self.failure_history_file = os.path.join(
            self.state_dir,
            "css_runtime_supervisor_failure_history.jsonl",
        )
        self.max_restart_limit = max_restart_limit
        self.failure_history_limit = max(1, int(failure_history_limit or 100))
        self.alert_service = alert_service or CSSAlertService()
        self.canonical_alert_bridge = canonical_alert_bridge or CanonicalAlertBridge()
        self.event_bus = event_bus

        self.started_at: Optional[str] = None
        self.stopped_at: Optional[str] = None
        self.last_heartbeat_at: Optional[str] = None
        self.failure_count: int = 0
        self.restart_count: int = 0
        self.restart_attempt_count: int = 0
        self.last_failure: Optional[str] = None
        self.failure_history: list[Dict[str, Any]] = []
        self.restart_limit_exhausted: bool = False
        self.process_generation: int = 0
        self.process_identity: Dict[str, Any] = {
            "launcher_pid": os.getpid(),
            "supervisor_pid": os.getpid(),
            "managed_services": {},
        }
        self.shutdown_requested: bool = False
        self.last_canonical_decision: Optional[Dict[str, Any]] = None
        self.last_decision_at: Optional[str] = None
        self.duplicate_canonical_owners: list[Dict[str, Any]] = []
        self.duplicate_discovery: Dict[str, Any] = {
            "ok": True,
            "owners": [],
            "error_code": None,
            "observed_at_utc": None,
        }
        self.last_persist_error: Optional[str] = None
        self.status: str = "STOPPED"

        self._ensure_state_dir()

    def _ensure_state_dir(self):
        validate_path_contained(self.state_dir, expected_root=self.trusted_root)
        os.makedirs(self.state_dir, exist_ok=True)
        validate_path_contained(self.state_dir, expected_root=self.trusted_root)

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
            if self.trusted_root is None:
                raise PersistenceError("supervisor_trusted_root_missing")
            atomic_write_json(self.state_file, state, expected_root=self.trusted_root)
            self.last_persist_error = None
        except PersistenceError as exc:
            self.last_persist_error = exc.code
            raise

    def _record_history(self, event: Dict[str, Any]) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "supervisor_id": self.supervisor_id,
            "process_generation": self.process_generation,
            "launcher_pid": self.process_identity.get("launcher_pid"),
            "supervisor_pid": self.process_identity.get("supervisor_pid"),
            "restart_count": self.restart_count,
            "restart_attempt_count": self.restart_attempt_count,
            "failure_count": self.failure_count,
            **event,
        }
        self.failure_history.append(record)
        if len(self.failure_history) > self.failure_history_limit:
            self.failure_history = self.failure_history[-self.failure_history_limit :]
        try:
            atomic_append_jsonl(self.failure_history_file, record, expected_root=self.trusted_root)
        except Exception:
            pass

    def record_process_tree(
        self,
        *,
        launcher_pid: int | None = None,
        supervisor_pid: int | None = None,
        managed_services: Optional[Dict[str, Any]] = None,
        launcher_parent_pid: int | None = None,
        launcher_creation_time: str | None = None,
        launcher_executable_path: str | None = None,
        launcher_executable_sha256: str | None = None,
        launcher_command_line: str | None = None,
        supervisor_parent_pid: int | None = None,
        supervisor_creation_time: str | None = None,
        supervisor_executable_path: str | None = None,
        supervisor_executable_sha256: str | None = None,
        supervisor_command_line: str | None = None,
        repo_root: str | None = None,
    ) -> None:
        identity: Dict[str, Any] = {
            "launcher_pid": int(launcher_pid or os.getpid()),
            "supervisor_pid": int(supervisor_pid or os.getpid()),
            "managed_services": dict(managed_services or {}),
        }
        if launcher_parent_pid is not None:
            identity["launcher_parent_pid"] = int(launcher_parent_pid)
        if launcher_creation_time is not None:
            identity["launcher_creation_time"] = launcher_creation_time
        if launcher_executable_path is not None:
            identity["launcher_executable_path"] = launcher_executable_path
        if launcher_executable_sha256 is not None:
            identity["launcher_executable_sha256"] = launcher_executable_sha256
        if launcher_command_line is not None:
            identity["launcher_command_line"] = launcher_command_line
        if supervisor_parent_pid is not None:
            identity["supervisor_parent_pid"] = int(supervisor_parent_pid)
        if supervisor_creation_time is not None:
            identity["supervisor_creation_time"] = supervisor_creation_time
        if supervisor_executable_path is not None:
            identity["supervisor_executable_path"] = supervisor_executable_path
        if supervisor_executable_sha256 is not None:
            identity["supervisor_executable_sha256"] = supervisor_executable_sha256
        if supervisor_command_line is not None:
            identity["supervisor_command_line"] = supervisor_command_line
        if repo_root is not None:
            identity["repo_root"] = repo_root
            identity["launcher_repo_root"] = repo_root
            identity["supervisor_repo_root"] = repo_root
        try:
            identity["launcher"] = build_process_identity_record(
                pid=identity["launcher_pid"],
                role="launcher",
                attempt_id="",
                baseline_commit="",
                repo_root=repo_root or "",
                parent_pid=identity.get("launcher_parent_pid"),
                creation_time=identity.get("launcher_creation_time"),
                executable_path=identity.get("launcher_executable_path"),
                executable_sha256=identity.get("launcher_executable_sha256"),
                command_line=identity.get("launcher_command_line"),
            )
            identity["supervisor"] = build_process_identity_record(
                pid=identity["supervisor_pid"],
                role="supervisor",
                attempt_id="",
                baseline_commit="",
                repo_root=repo_root or "",
                parent_pid=identity.get("supervisor_parent_pid"),
                creation_time=identity.get("supervisor_creation_time"),
                executable_path=identity.get("supervisor_executable_path"),
                executable_sha256=identity.get("supervisor_executable_sha256"),
                command_line=identity.get("supervisor_command_line"),
            )
            normalized_services: Dict[str, Any] = {}
            for name, info in dict(managed_services or {}).items():
                if isinstance(info, dict) and info.get("pid") is not None:
                    normalized_services[str(name)] = build_process_identity_record(
                        pid=info.get("pid"),
                        role=str(info.get("service_role") or info.get("role") or name),
                        attempt_id="",
                        baseline_commit="",
                        repo_root=repo_root or info.get("repo_root") or "",
                        parent_pid=info.get("parent_pid"),
                        creation_time=info.get("creation_time") or info.get("create_time"),
                        executable_path=info.get("executable_path") or info.get("exe"),
                        executable_sha256=info.get("executable_sha256"),
                        command_line=info.get("command_line") or info.get("cmdline"),
                    )
                else:
                    normalized_services[str(name)] = info
            identity["managed_services"] = normalized_services
        except Exception as exc:
            identity["process_identity_error"] = f"{type(exc).__name__}:{exc}"
        self.process_identity = identity
        self._persist_state()

    def _safe_publish_event(
        self,
        event_type: str,
        severity: str,
        category: str,
        payload: Dict[str, Any],
    ) -> None:
        if not self.event_bus:
            return
        try:
            from backend.events.event_models import Event
            event = Event(
                event_type=event_type,
                severity=severity,
                category=category,
                source="css_runtime_supervisor",
                payload=payload,
            )
            self.event_bus.publish(event)
        except Exception:
            pass

    def start(self):
        self.status = "RUNNING"
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.stopped_at = None
        self.shutdown_requested = False
        self.record_process_tree()
        self._persist_state()
        self._safe_emit("Supervisor started", AlertSeverity.INFO)
        self._safe_publish_event(
            event_type="RUNTIME_STARTED",
            severity="INFO",
            category="SYSTEM",
            payload={"supervisor_id": self.supervisor_id, "started_at": self.started_at}
        )

    def stop(self):
        self.status = "STOPPED"
        self.stopped_at = datetime.now(timezone.utc).isoformat()
        self.shutdown_requested = True
        self._record_history(
            {
                "event_type": "controlled_shutdown",
                "reason": "shutdown_requested",
                "status": self.status,
                "stopped_at": self.stopped_at,
            }
        )
        self._persist_state()
        self._safe_emit("Supervisor stopped", AlertSeverity.INFO)
        self._safe_publish_event(
            event_type="RUNTIME_STOPPED",
            severity="INFO",
            category="SYSTEM",
            payload={"supervisor_id": self.supervisor_id, "stopped_at": self.stopped_at}
        )

    def heartbeat(self):
        self.last_heartbeat_at = datetime.now(timezone.utc).isoformat()
        self._persist_state()

    def record_canonical_decision(self, canonical_decision: Dict[str, Any]) -> None:
        if not isinstance(canonical_decision, dict):
            return
        self.last_canonical_decision = dict(canonical_decision)
        self.last_decision_at = datetime.now(timezone.utc).isoformat()
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
            self._safe_publish_event(
                event_type="HEARTBEAT_LOST",
                severity="CRITICAL",
                category="SYSTEM",
                payload={
                    "supervisor_id": self.supervisor_id,
                    "last_heartbeat_at": self.last_heartbeat_at,
                    "stale_threshold_seconds": stale_threshold_seconds,
                    "elapsed_seconds": (now_dt - last_dt).total_seconds(),
                }
            )

            try:
                self.canonical_alert_bridge.record_heartbeat_stale(
                    source="css_runtime_supervisor",
                    message="Heartbeat stale detected",
                    details={
                        "stale_threshold_seconds": int(stale_threshold_seconds),
                        "last_heartbeat_at": self.last_heartbeat_at,
                    },
                    dedupe_key=(
                        f"HEARTBEAT_STALE:css_runtime_supervisor:"
                        f"{self.last_heartbeat_at}"
                    ),
                )
            except Exception:
                pass
            return True

        return False

    def record_failure(
        self,
        reason: str,
        *,
        service_name: str | None = None,
        pid_before: int | None = None,
        exit_code: int | None = None,
    ):
        self.failure_count += 1
        self.last_failure = reason
        self.status = (
            "FAILED"
            if self.restart_count >= self.max_restart_limit
            or self.restart_attempt_count >= self.max_restart_limit
            else "DEGRADED"
        )
        self.restart_limit_exhausted = (
            self.restart_count >= self.max_restart_limit
            or self.restart_attempt_count >= self.max_restart_limit
        )

        self._record_history(
            {
                "event_type": "unexpected_failure",
                "reason": reason,
                "service_name": service_name,
                "pid_before": pid_before,
                "pid_after": None,
                "exit_code": exit_code,
                "status": self.status,
                "max_restart_limit": self.max_restart_limit,
                "restart_limit_exhausted": self.restart_limit_exhausted,
            }
        )

        self._persist_state()

        self._safe_emit(
            f"Failure recorded: {reason}",
            AlertSeverity.WARNING,
            {
                "reason": reason,
                "failure_count": self.failure_count,
                "restart_count": self.restart_count,
                "restart_attempt_count": self.restart_attempt_count,
                "max_restart_limit": self.max_restart_limit,
                "restart_limit_exhausted": self.restart_limit_exhausted,
            },
        )

        try:
            self.canonical_alert_bridge.record_runtime_failure(
                source="css_runtime_supervisor",
                message=f"Runtime failure: {reason}",
                details={
                    "reason": reason,
                    "failure_count": self.failure_count,
                    "restart_count": self.restart_count,
                    "restart_attempt_count": self.restart_attempt_count,
                    "max_restart_limit": self.max_restart_limit,
                    "status": self.status,
                },
                dedupe_key=(
                    f"RUNTIME_FAILURE:css_runtime_supervisor:{reason}:"
                    f"{self.failure_count}"
                ),
            )
        except Exception:
            pass

    def should_restart(self) -> bool:
        if self.status in ("FAILED", "DEGRADED"):
            return (
                self.restart_count < self.max_restart_limit
                and self.restart_attempt_count < self.max_restart_limit
            )
        return False

    def record_restart(
        self,
        *,
        service_name: str | None = None,
        pid_before: int | None = None,
        pid_after: int | None = None,
        reason: str = "unexpected_restart_success",
    ):
        if self.restart_count >= self.max_restart_limit:
            self.record_restart_exhausted(service_name or "CSS Runtime")
            return

        prior_generation = self.process_generation
        self.restart_count += 1
        self.process_generation += 1
        self.failure_count = 0
        self.last_failure = None
        self.status = "RUNNING"
        self.restart_limit_exhausted = self.restart_count >= self.max_restart_limit
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.stopped_at = None
        if service_name:
            services = dict(self.process_identity.get("managed_services") or {})
            services[service_name] = {
                "pid": pid_after,
                "started_at": self.started_at,
                "generation": self.process_generation,
            }
            self.process_identity["managed_services"] = services

        self._record_history(
            {
                "event_type": "unexpected_restart_success",
                "reason": reason,
                "service_name": service_name,
                "pid_before": pid_before,
                "pid_after": pid_after,
                "prior_process_generation": prior_generation,
                "status": self.status,
                "max_restart_limit": self.max_restart_limit,
                "restart_limit_exhausted": self.restart_limit_exhausted,
            }
        )

        self._persist_state()

        self._safe_emit(
            "Restart recorded",
            AlertSeverity.INFO,
            {
                "restart_count": self.restart_count,
                "failure_count_reset": True,
                "process_generation": self.process_generation,
                "pid_before": pid_before,
                "pid_after": pid_after,
                "restart_limit_exhausted": self.restart_limit_exhausted,
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
        self.restart_attempt_count += 1
        self.restart_limit_exhausted = self.restart_attempt_count >= self.max_restart_limit
        if self.restart_limit_exhausted:
            self.status = "FAILED"
        self._record_history(
            {
                "event_type": "restart_attempt",
                "reason": "unexpected_restart_attempt",
                "service_name": service_name,
                "attempt": attempt,
                "backoff_seconds": delay_seconds,
                "status": self.status,
                "max_restart_limit": self.max_restart_limit,
                "restart_limit_exhausted": self.restart_limit_exhausted,
            }
        )
        self._persist_state()

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
                "restart_attempt_count": self.restart_attempt_count,
                "max_restart_limit": self.max_restart_limit,
                "backoff_seconds": delay_seconds,
                "restart_limit_exhausted": self.restart_limit_exhausted,
            },
        )
        self._safe_publish_event(
            event_type="RECOVERY_STARTED",
            severity="WARNING",
            category="SYSTEM",
            payload={
                "supervisor_id": self.supervisor_id,
                "service_name": service_name,
                "attempt": attempt,
                "restart_attempt_count": self.restart_attempt_count,
                "max_restart_limit": self.max_restart_limit,
                "delay_seconds": delay_seconds,
            }
        )

    def record_restart_success(
        self,
        service_name: str,
        attempt: int,
        *,
        pid_before: int | None = None,
        pid_after: int | None = None,
    ):
        if self.restart_count >= self.max_restart_limit:
            self.record_restart_exhausted(service_name)
            return

        msg = (
            f"Service '{service_name}' restarted successfully "
            f"(attempt {attempt})"
        )

        print(f"[SUPERVISOR] {msg}")

        self.record_restart(
            service_name=service_name,
            pid_before=pid_before,
            pid_after=pid_after,
        )

        self._safe_emit(
            msg,
            AlertSeverity.INFO,
            {
                "service_name": service_name,
                "attempt": attempt,
                "total_restarts": self.restart_count,
                "failure_count": self.failure_count,
                "pid_before": pid_before,
                "pid_after": pid_after,
                "process_generation": self.process_generation,
                "restart_limit_exhausted": self.restart_limit_exhausted,
            },
        )

        try:
            self.canonical_alert_bridge.record_supervisor_recovery(
                source="css_runtime_supervisor",
                message=msg,
                details={
                    "service_name": service_name,
                    "attempt": int(attempt),
                    "restart_count": self.restart_count,
                    "process_generation": self.process_generation,
                },
                dedupe_key=(
                    f"SUPERVISOR_RECOVERY:css_runtime_supervisor:"
                    f"{service_name}:{attempt}"
                ),
            )
        except Exception:
            pass

        self._safe_publish_event(
            event_type="RECOVERY_COMPLETE",
            severity="INFO",
            category="SYSTEM",
            payload={
                "supervisor_id": self.supervisor_id,
                "service_name": service_name,
                "attempt": attempt,
                "restart_count": self.restart_count,
            }
        )

    def record_restart_exhausted(self, service_name: str):
        msg = (
            f"Service '{service_name}' restart limit exhausted "
            f"({self.max_restart_limit} attempts). Service will not be "
            f"restarted automatically. Manual intervention required."
        )

        print(f"[SUPERVISOR] CRITICAL: {msg}")

        self.status = "FAILED"
        self.restart_limit_exhausted = True
        self._record_history(
            {
                "event_type": "restart_limit_exhausted",
                "reason": "max_restart_limit_exhausted",
                "service_name": service_name,
                "status": self.status,
                "max_restart_limit": self.max_restart_limit,
                "restart_limit_exhausted": self.restart_limit_exhausted,
            }
        )
        self._persist_state()

        self._safe_emit(
            msg,
            AlertSeverity.CRITICAL,
            {
                "service_name": service_name,
                "max_restart_limit": self.max_restart_limit,
                "failure_count": self.failure_count,
                "restart_count": self.restart_count,
                "restart_attempt_count": self.restart_attempt_count,
                "process_generation": self.process_generation,
                "restart_limit_exhausted": self.restart_limit_exhausted,
            },
        )

    def record_duplicate_discovery(self, result: dict[str, Any]) -> None:
        if not isinstance(result, dict):
            raise ValueError("duplicate_discovery result must be a dict")
        ok = bool(result.get("ok"))
        owners = list(result.get("owners") or [])
        error_code = result.get("error_code")
        self.duplicate_discovery = {
            "ok": ok,
            "owners": owners,
            "error_code": str(error_code) if error_code not in (None, "") else None,
            "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        if ok and owners:
            self.duplicate_canonical_owners = owners
        elif ok and not owners:
            self.duplicate_canonical_owners = []
        self._persist_state()

    def record_duplicate_canonical_owners(self, owners: list[Dict[str, Any]] | None) -> None:
        owner_list = list(owners or [])
        self.duplicate_canonical_owners = owner_list
        self.record_duplicate_discovery(
            {
                "ok": True,
                "owners": owner_list,
                "error_code": None,
            }
        )

    def get_status(self) -> Dict[str, Any]:
        return {
            "supervisor_id": self.supervisor_id,
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
            "last_heartbeat_at": self.last_heartbeat_at,
            "failure_count": self.failure_count,
            "restart_count": self.restart_count,
            "restart_attempt_count": self.restart_attempt_count,
            "last_failure": self.last_failure,
            "failure_history": list(self.failure_history),
            "failure_history_limit": self.failure_history_limit,
            "failure_history_path": self.failure_history_file,
            "restart_limit_exhausted": self.restart_limit_exhausted,
            "process_generation": self.process_generation,
            "process_identity": dict(self.process_identity),
            "duplicate_canonical_owners": list(self.duplicate_canonical_owners),
            "duplicate_discovery": dict(self.duplicate_discovery),
            "last_persist_error": self.last_persist_error,
            "shutdown_requested": self.shutdown_requested,
            "last_canonical_decision": self.last_canonical_decision,
            "last_decision_at": self.last_decision_at,
            "status": self.status,
            "max_restart_limit": self.max_restart_limit,
        }
