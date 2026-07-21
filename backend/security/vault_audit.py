"""Append-only metadata audit for credential-governance events."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import threading
import uuid
from typing import Any, Mapping

from backend.security.vault_models import utc_now
from backend.security.vault_redaction import redact_value


@dataclass(frozen=True)
class VaultAuditEvent:
    timestamp: str
    operator: str
    service: str
    broker: str
    credential_id: str
    correlation_id: str
    action: str
    success: bool
    reason_code: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class VaultAuditLog:
    def __init__(self, path: str | Path | None = None):
        self._path = Path(path) if path is not None else None
        self._events: list[VaultAuditEvent] = []
        self._lock = threading.RLock()

    def record(
        self,
        *,
        operator: str,
        service: str,
        broker: str,
        credential_id: str,
        action: str,
        success: bool,
        reason_code: str,
        correlation_id: str | None = None,
    ) -> VaultAuditEvent:
        event = VaultAuditEvent(
            timestamp=utc_now(),
            operator=str(operator or "SYSTEM"),
            service=str(service or "UNKNOWN"),
            broker=str(broker or "NONE").upper(),
            credential_id=str(credential_id or "UNASSIGNED"),
            correlation_id=str(correlation_id or uuid.uuid4()),
            action=str(action or "UNKNOWN").upper(),
            success=bool(success),
            reason_code=str(reason_code or "NONE").upper(),
        )
        safe = redact_value(event.as_dict())
        if "[REDACTED]" in safe.values():
            raise ValueError("AUDIT_METADATA_CONTAINS_SENSITIVE_FIELD")
        with self._lock:
            self._events.append(event)
            if self._path is not None:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                with self._path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(safe, sort_keys=True) + "\n")
        return event

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            return [event.as_dict() for event in self._events[-max(0, int(limit)) :]]


__all__ = ["VaultAuditEvent", "VaultAuditLog"]
