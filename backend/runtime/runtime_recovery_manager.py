from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from backend.monitoring.alert_bridge import CanonicalAlertBridge


@dataclass(frozen=True)
class RecoveryAttempt:
    recovery_type: str
    attempt_number: int
    success: bool
    timestamp: str
    reason: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RecoveryState:
    recovery_type: str
    max_retries: int
    attempts: tuple[RecoveryAttempt, ...]
    successful: bool
    exhausted: bool
    last_error: str


@dataclass(frozen=True)
class RecoveryResult:
    recovery_type: str
    success: bool
    attempts_used: int
    exhausted: bool
    reason: str
    state: RecoveryState


class RuntimeRecoveryManager:
    """Coordinates fail-closed runtime recovery attempts with canonical alerts."""

    DEFAULT_MAX_RETRIES: dict[str, int] = {
        "runtime_restart": 3,
        "supervisor": 2,
        "heartbeat": 2,
        "session": 2,
        "repository": 2,
    }

    def __init__(
        self,
        *,
        alert_bridge: CanonicalAlertBridge | None = None,
        max_retries: dict[str, int] | None = None,
    ) -> None:
        self.alert_bridge = alert_bridge or CanonicalAlertBridge()
        merged = dict(self.DEFAULT_MAX_RETRIES)
        if max_retries:
            for recovery_type, retries in max_retries.items():
                merged[str(recovery_type)] = max(1, int(retries))
        self.max_retries = merged

    def recover_runtime_restart(
        self,
        recovery_action: Callable[[int], bool | dict[str, Any]],
    ) -> RecoveryResult:
        return self._recover_with_policy(
            recovery_type="runtime_restart",
            recovery_action=recovery_action,
            on_success_event_type=None,
            on_success_message="Runtime restart recovery succeeded",
        )

    def recover_supervisor(
        self,
        recovery_action: Callable[[int], bool | dict[str, Any]],
    ) -> RecoveryResult:
        return self._recover_with_policy(
            recovery_type="supervisor",
            recovery_action=recovery_action,
            on_success_event_type="SUPERVISOR_RECOVERY",
            on_success_message="Supervisor recovery succeeded",
        )

    def recover_heartbeat(
        self,
        recovery_action: Callable[[int], bool | dict[str, Any]],
    ) -> RecoveryResult:
        return self._recover_with_policy(
            recovery_type="heartbeat",
            recovery_action=recovery_action,
            on_success_event_type="HEARTBEAT_RECOVERY",
            on_success_message="Heartbeat recovery succeeded",
        )

    def recover_session(
        self,
        recovery_action: Callable[[int], bool | dict[str, Any]],
    ) -> RecoveryResult:
        return self._recover_with_policy(
            recovery_type="session",
            recovery_action=recovery_action,
            on_success_event_type="SESSION_RECOVERY",
            on_success_message="Session recovery succeeded",
        )

    def recover_repository(
        self,
        recovery_action: Callable[[int], bool | dict[str, Any]],
    ) -> RecoveryResult:
        return self._recover_with_policy(
            recovery_type="repository",
            recovery_action=recovery_action,
            on_success_event_type=None,
            on_success_message="Repository recovery succeeded",
        )

    def _recover_with_policy(
        self,
        *,
        recovery_type: str,
        recovery_action: Callable[[int], bool | dict[str, Any]],
        on_success_event_type: str | None,
        on_success_message: str,
    ) -> RecoveryResult:
        attempts: list[RecoveryAttempt] = []
        retry_limit = int(self.max_retries.get(recovery_type, 1))

        for attempt_number in range(1, retry_limit + 1):
            success = False
            reason = "RECOVERY_ACTION_RETURNED_FALSE"
            details: dict[str, Any] = {}

            try:
                action_result = recovery_action(attempt_number)
                success, reason, details = self._parse_action_result(action_result)
            except Exception as exc:
                success = False
                reason = f"RECOVERY_ACTION_EXCEPTION:{type(exc).__name__}"
                details = {"error": str(exc)}

            attempts.append(
                RecoveryAttempt(
                    recovery_type=recovery_type,
                    attempt_number=attempt_number,
                    success=success,
                    timestamp=self._utc_timestamp(),
                    reason=reason,
                    details=details,
                )
            )

            if success:
                emit_reason = self._emit_recovery_success(
                    recovery_type=recovery_type,
                    on_success_event_type=on_success_event_type,
                    on_success_message=on_success_message,
                    attempts=attempts,
                )
                if emit_reason is not None:
                    # Fail closed: successful recovery without canonical alert emission is treated as failure.
                    attempts.append(
                        RecoveryAttempt(
                            recovery_type=recovery_type,
                            attempt_number=attempt_number,
                            success=False,
                            timestamp=self._utc_timestamp(),
                            reason=emit_reason,
                            details={"stage": "alert_emission"},
                        )
                    )
                    break

                return RecoveryResult(
                    recovery_type=recovery_type,
                    success=True,
                    attempts_used=attempt_number,
                    exhausted=False,
                    reason="RECOVERY_SUCCESS",
                    state=RecoveryState(
                        recovery_type=recovery_type,
                        max_retries=retry_limit,
                        attempts=tuple(attempts),
                        successful=True,
                        exhausted=False,
                        last_error="",
                    ),
                )

        last_error = attempts[-1].reason if attempts else "RECOVERY_NOT_ATTEMPTED"
        self._emit_recovery_failure(
            recovery_type=recovery_type,
            attempts=attempts,
            reason=last_error,
        )

        return RecoveryResult(
            recovery_type=recovery_type,
            success=False,
            attempts_used=len(attempts),
            exhausted=True,
            reason=last_error,
            state=RecoveryState(
                recovery_type=recovery_type,
                max_retries=retry_limit,
                attempts=tuple(attempts),
                successful=False,
                exhausted=True,
                last_error=last_error,
            ),
        )

    def _emit_recovery_success(
        self,
        *,
        recovery_type: str,
        on_success_event_type: str | None,
        on_success_message: str,
        attempts: list[RecoveryAttempt],
    ) -> str | None:
        try:
            details = {
                "recovery_type": recovery_type,
                "attempts_used": len(attempts),
                "last_attempt_reason": attempts[-1].reason if attempts else "",
            }

            if on_success_event_type:
                self.alert_bridge.emit(
                    event_type=on_success_event_type,
                    severity="WARNING",
                    source="runtime_recovery_manager",
                    message=on_success_message,
                    details=details,
                    dedupe_key=(
                        f"{on_success_event_type}:runtime_recovery_manager:"
                        f"{recovery_type}:{len(attempts)}"
                    ),
                )

            self.alert_bridge.emit(
                event_type="RECOVERY_SUCCESS",
                severity="WARNING",
                source="runtime_recovery_manager",
                message=f"Recovery succeeded for {recovery_type}",
                details=details,
                dedupe_key=(
                    f"RECOVERY_SUCCESS:runtime_recovery_manager:"
                    f"{recovery_type}:{len(attempts)}"
                ),
            )
            return None
        except Exception as exc:
            return f"ALERT_EMISSION_FAILED:{type(exc).__name__}"

    def _emit_recovery_failure(
        self,
        *,
        recovery_type: str,
        attempts: list[RecoveryAttempt],
        reason: str,
    ) -> None:
        try:
            self.alert_bridge.emit(
                event_type="RECOVERY_FAILED",
                severity="CRITICAL",
                source="runtime_recovery_manager",
                message=f"Recovery failed for {recovery_type}",
                details={
                    "recovery_type": recovery_type,
                    "attempts_used": len(attempts),
                    "last_error": reason,
                },
                dedupe_key=(
                    f"RECOVERY_FAILED:runtime_recovery_manager:"
                    f"{recovery_type}:{reason}:{len(attempts)}"
                ),
            )
        except Exception:
            # Fail closed: escalation failure is swallowed to prevent recursive failure loops.
            pass

    def _parse_action_result(
        self,
        action_result: bool | dict[str, Any],
    ) -> tuple[bool, str, dict[str, Any]]:
        if isinstance(action_result, bool):
            if action_result:
                return True, "RECOVERY_ACTION_OK", {}
            return False, "RECOVERY_ACTION_RETURNED_FALSE", {}

        if isinstance(action_result, dict):
            success = bool(action_result.get("success", False))
            reason = str(action_result.get("reason", "RECOVERY_ACTION_RESULT"))
            details_raw = action_result.get("details", {})
            details = details_raw if isinstance(details_raw, dict) else {"details": details_raw}
            return success, reason, details

        return False, "RECOVERY_ACTION_INVALID_RESULT", {"result_type": type(action_result).__name__}

    def _utc_timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat()
