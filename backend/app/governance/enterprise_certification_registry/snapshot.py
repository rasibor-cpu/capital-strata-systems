"""Phase 191 — immutable registry snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from backend.app.governance.enterprise_certification_registry.hashing import RegistryHash
from backend.app.governance.enterprise_certification_registry.models import (
    FRAMEWORK_VERSION,
    SCHEMA_VERSION,
    CertificationRegistryEntry,
)
from backend.app.governance.enterprise_certification_registry.repository import RegistryRepository


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class RegistrySnapshot:
    schema_id: str
    schema_version: str
    framework_version: str
    timestamp: str
    entry_count: int
    snapshot_hash: str
    entries: tuple[CertificationRegistryEntry, ...]
    execution_authority: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "framework_version": self.framework_version,
            "timestamp": self.timestamp,
            "entry_count": self.entry_count,
            "snapshot_hash": self.snapshot_hash,
            "entries": [e.as_dict() for e in self.entries],
            "execution_authority": False,
        }

    def __post_init__(self) -> None:
        if self.execution_authority:
            raise ValueError("RegistrySnapshot must not grant execution_authority")

    @staticmethod
    def capture(
        repository: RegistryRepository,
        *,
        timestamp: str | None = None,
    ) -> "RegistrySnapshot":
        entries = repository.all_entries()
        digest = RegistryHash.hash_entries(entries)
        return RegistrySnapshot(
            schema_id="ENTERPRISE_CERTIFICATION_REGISTRY_SNAPSHOT",
            schema_version=SCHEMA_VERSION,
            framework_version=FRAMEWORK_VERSION,
            timestamp=timestamp or _utc_now(),
            entry_count=len(entries),
            snapshot_hash=digest,
            entries=entries,
            execution_authority=False,
        )
