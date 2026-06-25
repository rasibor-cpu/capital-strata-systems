from __future__ import annotations

from typing import Any

from backend.monitoring.alert_repository import AlertRepository


class CanonicalAlertBridge:
    """Writes runtime/supervisor events into the canonical alert repository."""

    def __init__(self, repository: AlertRepository | None = None) -> None:
        self.repository = repository or AlertRepository()

    def emit(
        self,
        *,
        event_type: str,
        severity: str,
        source: str,
        message: str,
        details: dict[str, Any] | None = None,
        dedupe_key: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "event_type": str(event_type or "").strip().upper(),
            "severity": str(severity or "").strip().upper(),
            "source": str(source or "").strip() or "unknown",
            "message": str(message or "").strip(),
            "details": details or {},
            "dedupe_key": str(dedupe_key or "").strip(),
        }
        return self.repository.persist_alert(payload)

    def record_supervisor_recovery(
        self,
        *,
        source: str,
        message: str,
        details: dict[str, Any] | None = None,
        dedupe_key: str | None = None,
    ) -> dict[str, Any]:
        return self.emit(
            event_type="SUPERVISOR_RECOVERY",
            severity="WARNING",
            source=source,
            message=message,
            details=details,
            dedupe_key=dedupe_key,
        )

    def record_runtime_failure(
        self,
        *,
        source: str,
        message: str,
        details: dict[str, Any] | None = None,
        dedupe_key: str | None = None,
    ) -> dict[str, Any]:
        return self.emit(
            event_type="RUNTIME_FAILURE",
            severity="CRITICAL",
            source=source,
            message=message,
            details=details,
            dedupe_key=dedupe_key,
        )

    def record_heartbeat_stale(
        self,
        *,
        source: str,
        message: str,
        details: dict[str, Any] | None = None,
        dedupe_key: str | None = None,
    ) -> dict[str, Any]:
        return self.emit(
            event_type="HEARTBEAT_STALE",
            severity="CRITICAL",
            source=source,
            message=message,
            details=details,
            dedupe_key=dedupe_key,
        )

    def record_broker_disconnect(
        self,
        *,
        source: str,
        message: str,
        details: dict[str, Any] | None = None,
        dedupe_key: str | None = None,
    ) -> dict[str, Any]:
        return self.emit(
            event_type="BROKER_DISCONNECT",
            severity="CRITICAL",
            source=source,
            message=message,
            details=details,
            dedupe_key=dedupe_key,
        )
