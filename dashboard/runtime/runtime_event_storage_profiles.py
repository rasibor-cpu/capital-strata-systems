from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


RUNTIME_EVENT_STORAGE_PROFILE_VERSION = "css.runtime_event_storage_profiles.v1"


@dataclass(frozen=True)
class RuntimeEventStorageBackendProfile:
    backend_name: str
    persistence_type: str
    durability_level: str
    queryability: str
    operational_complexity: str
    estimated_storage_multiplier: float
    recommended_for: tuple[str, ...]
    risks: tuple[str, ...]
    governance_notes: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["recommended_for"] = list(self.recommended_for)
        payload["risks"] = list(self.risks)
        payload["governance_notes"] = list(self.governance_notes)
        return payload


JSONL_APPEND_ONLY_PROFILE = RuntimeEventStorageBackendProfile(
    backend_name="jsonl_append_only",
    persistence_type="local_file_append_only",
    durability_level="LOCAL_MEDIUM",
    queryability="LOW_SCAN_BASED",
    operational_complexity="LOW",
    estimated_storage_multiplier=1.08,
    recommended_for=(
        "first approved local dry-run storage",
        "small-to-moderate event volumes",
        "human-readable incident review",
    ),
    risks=(
        "large files require scanning",
        "corruption handling must skip malformed lines safely",
        "concurrent writer locking must be explicit",
    ),
    governance_notes=(
        "must remain append-only",
        "requires redaction before write",
        "requires approved retention window",
    ),
)

SQLITE_LOCAL_INDEXED_PROFILE = RuntimeEventStorageBackendProfile(
    backend_name="sqlite_local_indexed",
    persistence_type="local_sqlite_indexed_store",
    durability_level="LOCAL_HIGH",
    queryability="HIGH_INDEXED",
    operational_complexity="MEDIUM",
    estimated_storage_multiplier=1.35,
    recommended_for=(
        "operator filtering by subsystem, timestamp, severity, and correlation id",
        "larger local event volumes",
        "repeatable incident and release review",
    ),
    risks=(
        "schema migrations require governance",
        "database locking must be tested",
        "corruption recovery needs an operator procedure",
    ),
    governance_notes=(
        "schema must be versioned",
        "writes require explicit approval",
        "indexes must not store unredacted payload fragments",
    ),
)

STRUCTURED_APPEND_LOG_PROFILE = RuntimeEventStorageBackendProfile(
    backend_name="structured_append_log",
    persistence_type="local_structured_append_log",
    durability_level="LOCAL_HIGH",
    queryability="MEDIUM_TIMELINE_ORIENTED",
    operational_complexity="MEDIUM_HIGH",
    estimated_storage_multiplier=1.2,
    recommended_for=(
        "event lineage and deterministic replay foundations",
        "strict append-only audit-style storage",
        "checkpointed reconstruction planning",
    ),
    risks=(
        "requires log compaction design",
        "operator tooling must be built before production use",
        "format changes require compatibility tests",
    ),
    governance_notes=(
        "event ordering must be stable",
        "correlation identifiers are mandatory",
        "checkpoint metadata must be audit-safe",
    ),
)

FUTURE_EXTERNAL_STREAM_PROFILE = RuntimeEventStorageBackendProfile(
    backend_name="future_external_queue_stream",
    persistence_type="external_queue_or_stream",
    durability_level="EXTERNAL_CONFIGURED",
    queryability="HIGH_DEPENDS_ON_PLATFORM",
    operational_complexity="HIGH",
    estimated_storage_multiplier=1.5,
    recommended_for=(
        "future multi-process deployment",
        "sanitized companion-app feeds",
        "centralized observability after local persistence is proven",
    ),
    risks=(
        "introduces infrastructure credentials",
        "requires network and incident-response governance",
        "not appropriate before local storage is certified",
    ),
    governance_notes=(
        "must not be first persistence backend",
        "requires separate security review",
        "requires explicit operator and deployment approval",
    ),
)

DEFAULT_RUNTIME_EVENT_STORAGE_BACKEND_PROFILES = (
    JSONL_APPEND_ONLY_PROFILE,
    SQLITE_LOCAL_INDEXED_PROFILE,
    STRUCTURED_APPEND_LOG_PROFILE,
    FUTURE_EXTERNAL_STREAM_PROFILE,
)


def get_runtime_event_storage_profiles_payload(
    profiles: tuple[
        RuntimeEventStorageBackendProfile,
        ...,
    ] = DEFAULT_RUNTIME_EVENT_STORAGE_BACKEND_PROFILES,
) -> dict[str, Any]:
    return {
        "payload_version": RUNTIME_EVENT_STORAGE_PROFILE_VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "simulation_only": True,
        "persistence_enabled": False,
        "writes_performed": False,
        "profiles": [profile.as_dict() for profile in profiles],
    }


__all__ = [
    "DEFAULT_RUNTIME_EVENT_STORAGE_BACKEND_PROFILES",
    "FUTURE_EXTERNAL_STREAM_PROFILE",
    "JSONL_APPEND_ONLY_PROFILE",
    "RUNTIME_EVENT_STORAGE_PROFILE_VERSION",
    "RuntimeEventStorageBackendProfile",
    "SQLITE_LOCAL_INDEXED_PROFILE",
    "STRUCTURED_APPEND_LOG_PROFILE",
    "get_runtime_event_storage_profiles_payload",
]
