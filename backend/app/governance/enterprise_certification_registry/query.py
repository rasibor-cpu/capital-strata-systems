"""Phase 191 — registry query surface."""

from __future__ import annotations

from backend.app.governance.enterprise_certification_registry.models import CertificationRegistryEntry
from backend.app.governance.enterprise_certification_registry.repository import RegistryRepository


class RegistryQuery:
    def __init__(self, repository: RegistryRepository) -> None:
        self._repo = repository

    def by_id(self, registry_id: str) -> CertificationRegistryEntry | None:
        return self._repo.get(registry_id)

    def by_entity_type(self, entity_type: str) -> tuple[CertificationRegistryEntry, ...]:
        key = str(entity_type).upper()
        return tuple(e for e in self._repo.all_entries() if e.entity_type == key)

    def by_broker(self, broker_type: str) -> tuple[CertificationRegistryEntry, ...]:
        key = str(broker_type).upper()
        return tuple(e for e in self._repo.all_entries() if e.broker_type == key)

    def by_asset_class(self, asset_class: str) -> tuple[CertificationRegistryEntry, ...]:
        key = str(asset_class).upper()
        return tuple(e for e in self._repo.all_entries() if e.asset_class == key)

    def by_phase(self, phase: str) -> tuple[CertificationRegistryEntry, ...]:
        needle = str(phase).upper()
        return tuple(
            e
            for e in self._repo.all_entries()
            if needle in {p.upper() for p in e.phase_refs} or needle in e.entity_name.upper()
        )

    def certified_readonly(self) -> tuple[CertificationRegistryEntry, ...]:
        return tuple(
            e
            for e in self._repo.all_entries()
            if e.read_only_status in {"CERTIFIED", "FRAMEWORK_READY"}
            and e.suspension_status == "ACTIVE"
            and e.execution_authority is False
        )

    def with_blockers(self) -> tuple[CertificationRegistryEntry, ...]:
        return tuple(e for e in self._repo.all_entries() if e.blocker_list)

    def claims_execution(self) -> tuple[CertificationRegistryEntry, ...]:
        # Should always be empty by invariant.
        return tuple(e for e in self._repo.all_entries() if e.execution_authority)
