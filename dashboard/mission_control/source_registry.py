from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any


SOURCE_LIVE = "LIVE"
SOURCE_RUNTIME = "RUNTIME"
SOURCE_RUNTIME_ENDPOINT = "RUNTIME_ENDPOINT"
SOURCE_RUNTIME_ARTIFACT = "RUNTIME_ARTIFACT"
SOURCE_RUNTIME_REGISTRY = "RUNTIME_REGISTRY"
SOURCE_CACHE = "CACHE"
SOURCE_HISTORICAL = "HISTORICAL"
SOURCE_MOCK = "MOCK"
SOURCE_DEMO = "DEMO"
SOURCE_UNAVAILABLE = "UNAVAILABLE"
SOURCE_UNKNOWN = "UNKNOWN"

SOURCE_STATUSES = frozenset(
    {
        SOURCE_LIVE,
        SOURCE_RUNTIME,
        SOURCE_RUNTIME_ENDPOINT,
        SOURCE_RUNTIME_ARTIFACT,
        SOURCE_RUNTIME_REGISTRY,
        SOURCE_CACHE,
        SOURCE_HISTORICAL,
        SOURCE_MOCK,
        SOURCE_DEMO,
        SOURCE_UNAVAILABLE,
        SOURCE_UNKNOWN,
    }
)


@dataclass(frozen=True)
class SourceDescriptor:
    section: str
    source: str
    source_module: str
    generated_at: str
    observed_at: str
    provenance: dict[str, Any]
    unavailable_reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


SECTION_SOURCE_MODULES: dict[str, str] = {
    "platform": "dashboard.runtime.frontend_contract",
    "runtime_snapshot": "dashboard.mission_control.runtime_snapshot_provider",
    "runtime": "dashboard.runtime.frontend_contract",
    "trading": "dashboard.runtime.frontend_contract",
    "portfolio": "dashboard.runtime.frontend_contract",
    "market_intelligence": "dashboard.runtime.frontend_contract",
    "risk": "dashboard.runtime.frontend_contract",
    "options_income": "dashboard.runtime.frontend_contract",
    "brokers": "backend.runtime.canonical_broker_runtime_state",
    "alerts": "dashboard.runtime.dashboard_state",
    "certification": "backend.runtime.runtime_certification_snapshot",
    "audit": "dashboard.runtime.frontend_contract",
    "explainability": "dashboard.runtime.frontend_contract",
    "learning": "dashboard.runtime.frontend_contract",
    "governance": "dashboard.runtime.frontend_contract",
    "configuration": "dashboard.runtime.frontend_contract",
    "documentation": "dashboard.mission_control.contracts",
    "permissions": "dashboard.mission_control.permissions",
    "safety": "dashboard.mission_control.safety",
}


def source_for_payload(
    section: str,
    frontend_payload: Mapping[str, Any],
    section_payload: Mapping[str, Any] | None = None,
    *,
    dashboard_state_available: bool,
    allow_mock: bool,
) -> dict[str, Any]:
    payload = section_payload if isinstance(section_payload, Mapping) else {}
    source = _source_status(frontend_payload, payload, dashboard_state_available=dashboard_state_available, allow_mock=allow_mock)
    generated_at = str(
        payload.get("generated_at")
        or payload.get("timestamp")
        or frontend_payload.get("generated_at")
        or "UNAVAILABLE"
    )
    observed_at = str(
        payload.get("observed_at")
        or payload.get("last_updated")
        or payload.get("last_successful_sync")
        or generated_at
    )
    provenance = payload.get("status_provenance") if isinstance(payload.get("status_provenance"), Mapping) else {}
    unavailable_reason = ""
    if source == SOURCE_UNAVAILABLE:
        unavailable_reason = str(payload.get("unavailable_reason") or payload.get("failure_reason") or "canonical_source_unavailable")
    return SourceDescriptor(
        section=section,
        source=source,
        source_module=SECTION_SOURCE_MODULES.get(section, "dashboard.mission_control"),
        generated_at=generated_at,
        observed_at=observed_at,
        provenance=dict(provenance),
        unavailable_reason=unavailable_reason,
    ).as_dict()


def build_source_registry(
    frontend_payload: Mapping[str, Any],
    state_sections: Mapping[str, Any],
    *,
    dashboard_state_available: bool,
    allow_mock: bool,
) -> dict[str, dict[str, Any]]:
    return {
        section: source_for_payload(
            section,
            frontend_payload,
            state_sections.get(section) if isinstance(state_sections.get(section), Mapping) else {},
            dashboard_state_available=dashboard_state_available,
            allow_mock=allow_mock,
        )
        for section in SECTION_SOURCE_MODULES
    }


def _source_status(
    frontend_payload: Mapping[str, Any],
    payload: Mapping[str, Any],
    *,
    dashboard_state_available: bool,
    allow_mock: bool,
) -> str:
    explicit = str(payload.get("data_source") or payload.get("source_status") or payload.get("source") or "").upper().strip()
    if explicit in SOURCE_STATUSES:
        return explicit

    frontend_source = str(frontend_payload.get("mission_control_data_source") or "").upper().strip()
    if frontend_source in SOURCE_STATUSES:
        return frontend_source

    if bool(frontend_payload.get("mission_control_mock_data")):
        return SOURCE_MOCK if allow_mock else SOURCE_UNAVAILABLE

    if dashboard_state_available:
        return SOURCE_RUNTIME

    return SOURCE_UNAVAILABLE


__all__ = [
    "SECTION_SOURCE_MODULES",
    "SOURCE_CACHE",
    "SOURCE_DEMO",
    "SOURCE_HISTORICAL",
    "SOURCE_LIVE",
    "SOURCE_MOCK",
    "SOURCE_RUNTIME",
    "SOURCE_RUNTIME_ARTIFACT",
    "SOURCE_RUNTIME_ENDPOINT",
    "SOURCE_RUNTIME_REGISTRY",
    "SOURCE_STATUSES",
    "SOURCE_UNAVAILABLE",
    "SOURCE_UNKNOWN",
    "build_source_registry",
    "source_for_payload",
]
