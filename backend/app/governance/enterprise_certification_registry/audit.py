"""Phase 191 — registry audit log view."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.app.governance.enterprise_certification_registry.repository import RegistryRepository


@dataclass(frozen=True)
class RegistryAuditReport:
    event_count: int
    events: tuple[dict[str, Any], ...]
    execution_authority_observed: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_count": self.event_count,
            "events": list(self.events),
            "execution_authority_observed": False,
        }


class RegistryAudit:
    def __init__(self, repository: RegistryRepository) -> None:
        self._repo = repository

    def report(self) -> RegistryAuditReport:
        events = self._repo.audit_events()
        return RegistryAuditReport(
            event_count=len(events),
            events=tuple(dict(e) for e in events),
            execution_authority_observed=False,
        )
