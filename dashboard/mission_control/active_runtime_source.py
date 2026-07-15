from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any


SOURCE_RUNTIME_ENDPOINT = "RUNTIME_ENDPOINT"
SOURCE_RUNTIME_ARTIFACT = "RUNTIME_ARTIFACT"
SOURCE_RUNTIME_REGISTRY = "RUNTIME_REGISTRY"
SOURCE_CACHE = "CACHE"
SOURCE_HISTORICAL = "HISTORICAL"
SOURCE_DEMO = "DEMO"
SOURCE_UNAVAILABLE = "UNAVAILABLE"

ACTIVE_RUNTIME_SOURCE_TYPES = frozenset(
    {
        SOURCE_RUNTIME_ENDPOINT,
        SOURCE_RUNTIME_ARTIFACT,
        SOURCE_RUNTIME_REGISTRY,
        SOURCE_CACHE,
        SOURCE_HISTORICAL,
        SOURCE_DEMO,
        SOURCE_UNAVAILABLE,
    }
)


@dataclass(frozen=True)
class RuntimeSourceCandidate:
    name: str
    source_type: str
    available: bool
    freshness_status: str
    path_category: str
    process_relationship: str
    generated_at: str = "UNAVAILABLE"
    observed_at: str = "UNAVAILABLE"
    failure: str = ""
    fallback_reason: str = ""
    state_hash: str = "UNAVAILABLE"
    metadata: dict[str, Any] = field(default_factory=dict)
    payload: Mapping[str, Any] | None = None

    def diagnostics(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("payload", None)
        data["execution_allowed"] = False
        data["live_trading_blocked"] = True
        data["broker_execution_armed"] = False
        data["advisory_only"] = True
        return data


def unavailable_candidate(name: str, *, source_type: str, failure: str, path_category: str = "NONE") -> RuntimeSourceCandidate:
    return RuntimeSourceCandidate(
        name=name,
        source_type=source_type,
        available=False,
        freshness_status="UNAVAILABLE",
        path_category=path_category,
        process_relationship="NONE",
        failure=failure,
    )


__all__ = [
    "ACTIVE_RUNTIME_SOURCE_TYPES",
    "RuntimeSourceCandidate",
    "SOURCE_CACHE",
    "SOURCE_DEMO",
    "SOURCE_HISTORICAL",
    "SOURCE_RUNTIME_ARTIFACT",
    "SOURCE_RUNTIME_ENDPOINT",
    "SOURCE_RUNTIME_REGISTRY",
    "SOURCE_UNAVAILABLE",
    "unavailable_candidate",
]
