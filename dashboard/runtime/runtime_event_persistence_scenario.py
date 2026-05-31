from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from dashboard.runtime.runtime_event_storage_profiles import (
    DEFAULT_RUNTIME_EVENT_STORAGE_BACKEND_PROFILES,
    RuntimeEventStorageBackendProfile,
)


RUNTIME_EVENT_PERSISTENCE_SCENARIO_VERSION = (
    "css.runtime_event_persistence_scenario.v1"
)


@dataclass(frozen=True)
class RuntimeEventPersistenceScenarioReport:
    recommended_backend: str
    recommendation_reasons: tuple[str, ...]
    governance_blockers: tuple[str, ...]
    backend_comparison: tuple[dict[str, Any], ...]
    scenario_summary: dict[str, Any]
    generated_utc: str
    persistence_enabled: bool = False
    writes_performed: bool = False
    simulation_only: bool = True
    read_only: bool = True
    payload_version: str = RUNTIME_EVENT_PERSISTENCE_SCENARIO_VERSION

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["recommendation_reasons"] = list(self.recommendation_reasons)
        payload["governance_blockers"] = list(self.governance_blockers)
        payload["backend_comparison"] = list(self.backend_comparison)
        return payload


def build_runtime_event_persistence_scenario_report(
    simulation_payload: dict[str, Any] | None = None,
    *,
    profiles: tuple[
        RuntimeEventStorageBackendProfile,
        ...,
    ] = DEFAULT_RUNTIME_EVENT_STORAGE_BACKEND_PROFILES,
) -> dict[str, Any]:
    simulation = simulation_payload or {}
    accepted = _safe_int(simulation.get("accepted_events_count"))
    rejected = _safe_int(simulation.get("rejected_events_count"))
    estimated_bytes = _safe_int(simulation.get("estimated_storage_bytes"))
    event_rate = _safe_float(simulation.get("estimated_event_rate"))
    redaction_failures = len(simulation.get("redaction_failures") or [])

    comparison = tuple(
        _compare_backend(
            profile,
            accepted_events=accepted,
            rejected_events=rejected,
            estimated_storage_bytes=estimated_bytes,
            event_rate=event_rate,
        )
        for profile in profiles
    )
    recommended = _recommend_backend(
        comparison,
        accepted_events=accepted,
        event_rate=event_rate,
    )
    blockers = _governance_blockers(
        simulation,
        rejected_events=rejected,
        redaction_failures=redaction_failures,
    )
    reasons = _recommendation_reasons(recommended, accepted, event_rate)

    return RuntimeEventPersistenceScenarioReport(
        recommended_backend=recommended,
        recommendation_reasons=reasons,
        governance_blockers=blockers,
        backend_comparison=comparison,
        scenario_summary={
            "accepted_events_count": accepted,
            "rejected_events_count": rejected,
            "redaction_failures_count": redaction_failures,
            "estimated_storage_bytes": estimated_bytes,
            "estimated_event_rate": event_rate,
            "simulation_id": str(simulation.get("simulation_id") or ""),
        },
        generated_utc=datetime.now(timezone.utc).isoformat(),
        persistence_enabled=False,
        writes_performed=False,
        simulation_only=True,
        read_only=True,
    ).as_dict()


def _compare_backend(
    profile: RuntimeEventStorageBackendProfile,
    *,
    accepted_events: int,
    rejected_events: int,
    estimated_storage_bytes: int,
    event_rate: float,
) -> dict[str, Any]:
    adjusted_bytes = int(round(estimated_storage_bytes * profile.estimated_storage_multiplier))
    risk_level = _risk_level(profile, rejected_events=rejected_events, event_rate=event_rate)
    suitability = _suitability(
        profile,
        accepted_events=accepted_events,
        rejected_events=rejected_events,
        event_rate=event_rate,
    )
    payload = profile.as_dict()
    payload.update(
        {
            "estimated_backend_storage_bytes": adjusted_bytes,
            "operational_risk": risk_level,
            "governance_suitability": suitability,
            "persistence_enabled": False,
            "writes_performed": False,
        }
    )
    return payload


def _recommend_backend(
    comparison: tuple[dict[str, Any], ...],
    *,
    accepted_events: int,
    event_rate: float,
) -> str:
    if accepted_events <= 0:
        return "jsonl_append_only"
    if event_rate >= 50:
        return "sqlite_local_indexed"
    for candidate in comparison:
        if candidate.get("backend_name") == "jsonl_append_only":
            return "jsonl_append_only"
    return str(comparison[0].get("backend_name")) if comparison else "NONE"


def _recommendation_reasons(
    recommended_backend: str,
    accepted_events: int,
    event_rate: float,
) -> tuple[str, ...]:
    if recommended_backend == "sqlite_local_indexed":
        return (
            "higher simulated event rate benefits from indexed local queries",
            "local-only storage keeps governance scope bounded",
            "external streams remain deferred until local certification",
        )
    if accepted_events <= 0:
        return (
            "no events are currently eligible for persistence",
            "jsonl append-only remains the simplest first backend once blockers clear",
            "storage selection remains provisional because persistence is disabled",
        )
    return (
        "jsonl append-only has the lowest first-step operational complexity",
        "local human-readable storage aligns with dry-run incident review",
        "indexed and external backends remain future options after approval",
    )


def _governance_blockers(
    simulation: dict[str, Any],
    *,
    rejected_events: int,
    redaction_failures: int,
) -> tuple[str, ...]:
    blockers = [
        "PERSISTENCE_DISABLED_BY_POLICY",
        "EXPLICIT_OPERATOR_APPROVAL_REQUIRED",
        "STORAGE_BACKEND_NOT_APPROVED",
        "PCNRASS_RELEASE_CHECK_REQUIRED_BEFORE_ACTIVATION",
    ]
    if rejected_events:
        blockers.append("SIMULATION_REJECTIONS_REQUIRE_REVIEW")
    if redaction_failures:
        blockers.append("REDACTION_FAILURES_REQUIRE_REMEDIATION")
    if simulation.get("writes_performed") is True:
        blockers.append("UNEXPECTED_WRITE_FLAG_REQUIRES_STOP")
    return tuple(dict.fromkeys(blockers))


def _risk_level(
    profile: RuntimeEventStorageBackendProfile,
    *,
    rejected_events: int,
    event_rate: float,
) -> str:
    if profile.operational_complexity == "HIGH":
        return "HIGH"
    if rejected_events or event_rate >= 50 or "MEDIUM_HIGH" in profile.operational_complexity:
        return "MEDIUM"
    return "LOW"


def _suitability(
    profile: RuntimeEventStorageBackendProfile,
    *,
    accepted_events: int,
    rejected_events: int,
    event_rate: float,
) -> str:
    if profile.backend_name == "future_external_queue_stream":
        return "DEFERRED_NOT_FIRST_BACKEND"
    if rejected_events:
        return "BLOCKED_UNTIL_SIMULATION_REJECTIONS_CLEAR"
    if accepted_events <= 0:
        return "PROVISIONAL_NO_ACCEPTED_EVENTS"
    if profile.backend_name == "sqlite_local_indexed" and event_rate >= 50:
        return "STRONG_FOR_HIGH_RATE_LOCAL_REVIEW"
    if profile.backend_name == "jsonl_append_only":
        return "STRONG_FOR_FIRST_APPROVED_LOCAL_BACKEND"
    return "CANDIDATE_AFTER_LOCAL_BASELINE"


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


__all__ = [
    "RUNTIME_EVENT_PERSISTENCE_SCENARIO_VERSION",
    "RuntimeEventPersistenceScenarioReport",
    "build_runtime_event_persistence_scenario_report",
]
