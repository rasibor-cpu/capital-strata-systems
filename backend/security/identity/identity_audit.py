"""Append-only enterprise identity access audit."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import threading
import uuid
from typing import Any

from backend.security.identity.identity_models import utc_now
from backend.security.vault_redaction import redact_text, redact_value


@dataclass(frozen=True)
class IdentityAuditEntry:
    audit_id: str
    timestamp: str
    who: str
    role: str
    resource_id: str
    why: str
    component: str
    duration_seconds: int
    reason: str
    result: str
    correlation_id: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class IdentityAuditLedger:
    def __init__(self, path: str | Path | None = None):
        self._entries: list[IdentityAuditEntry] = []
        self._path = Path(path) if path else None
        self._lock = threading.RLock()

    def append(
        self,
        *,
        who: str,
        role: str,
        resource_id: str,
        why: str,
        component: str,
        duration_seconds: int,
        reason: str,
        result: str,
        correlation_id: str | None = None,
    ) -> IdentityAuditEntry:
        entry = IdentityAuditEntry(
            audit_id=str(uuid.uuid4()),
            timestamp=utc_now(),
            who=str(who),
            role=str(role).upper(),
            resource_id=str(resource_id),
            why=redact_text(why)[:256],
            component=redact_text(component)[:128],
            duration_seconds=max(0, int(duration_seconds)),
            reason=redact_text(reason).upper()[:128],
            result=str(result).upper(),
            correlation_id=str(correlation_id or uuid.uuid4()),
        )
        safe = redact_value(entry.as_dict())
        with self._lock:
            self._entries.append(entry)
            if self._path:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                with self._path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(safe, sort_keys=True) + "\n")
        return entry

    def entries(self, *, resource_id: str | None = None) -> tuple[IdentityAuditEntry, ...]:
        with self._lock:
            rows = self._entries
            if resource_id is not None:
                rows = [row for row in rows if row.resource_id == resource_id]
            return tuple(rows)


__all__ = ["IdentityAuditEntry", "IdentityAuditLedger"]
