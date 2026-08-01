"""Phase 191 — immutable-in-content registry repository."""

from __future__ import annotations

from typing import Iterable, Iterator

from backend.app.governance.enterprise_certification_registry.models import CertificationRegistryEntry
from backend.app.governance.enterprise_certification_registry.validator import RegistryValidator


class RegistryRepository:
    """In-memory authoritative store. Entries themselves are immutable."""

    def __init__(self, *, validator: RegistryValidator | None = None) -> None:
        self._validator = validator or RegistryValidator()
        self._entries: dict[str, CertificationRegistryEntry] = {}
        self._audit_events: list[dict[str, object]] = []

    def register(self, entry: CertificationRegistryEntry) -> CertificationRegistryEntry:
        result = self._validator.validate_entry(entry)
        if not result.ok:
            raise ValueError(f"invalid registry entry: {','.join(result.errors)}")
        if entry.registry_id in self._entries:
            raise ValueError(f"registry_id already exists: {entry.registry_id}")
        self._entries[entry.registry_id] = entry
        self._audit_events.append(
            {
                "event": "REGISTERED",
                "registry_id": entry.registry_id,
                "entity_type": entry.entity_type,
                "entity_name": entry.entity_name,
                "execution_authority": False,
            }
        )
        return entry

    def get(self, registry_id: str) -> CertificationRegistryEntry | None:
        return self._entries.get(registry_id)

    def require(self, registry_id: str) -> CertificationRegistryEntry:
        entry = self.get(registry_id)
        if entry is None:
            raise KeyError(f"registry entry not found: {registry_id}")
        return entry

    def all_entries(self) -> tuple[CertificationRegistryEntry, ...]:
        return tuple(sorted(self._entries.values(), key=lambda e: e.registry_id))

    def __iter__(self) -> Iterator[CertificationRegistryEntry]:
        return iter(self.all_entries())

    def __len__(self) -> int:
        return len(self._entries)

    def audit_events(self) -> tuple[dict[str, object], ...]:
        return tuple(self._audit_events)

    def extend(self, entries: Iterable[CertificationRegistryEntry]) -> int:
        count = 0
        for entry in entries:
            self.register(entry)
            count += 1
        return count
