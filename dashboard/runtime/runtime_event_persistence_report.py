from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from dashboard.runtime.runtime_event_inspector import (
    DEFAULT_RUNTIME_EVENT_RETENTION_POLICY,
    RuntimeEventRetentionPolicy,
)
from dashboard.runtime.runtime_event_persistence_policy import (
    DEFAULT_RUNTIME_EVENT_PERSISTENCE_POLICY,
    RuntimeEventPersistencePolicy,
)
from dashboard.runtime.runtime_event_persistence_scenario import (
    build_runtime_event_persistence_scenario_report,
)


RUNTIME_EVENT_PERSISTENCE_REPORT_VERSION = (
    "css.runtime_event_persistence_report.v1"
)


@dataclass(frozen=True)
class RuntimeEventPersistenceDryRunReport:
    report_id: str
    generated_at_utc: str
    simulation_only: bool
    persistence_enabled: bool
    writes_performed: bool
    read_only: bool
    retention_policy_summary: dict[str, Any]
    persistence_approval_policy_summary: dict[str, Any]
    simulator_summary: dict[str, Any]
    backend_scenario_comparison: list[dict[str, Any]]
    recommended_backend: str
    governance_blockers: list[str]
    safety_assertions: list[str]
    pcnrass_readiness_notes: list[str]
    remaining_approval_requirements: list[str]
    export_format: str = "json"
    payload_version: str = RUNTIME_EVENT_PERSISTENCE_REPORT_VERSION

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_runtime_event_persistence_report(
    simulation_payload: dict[str, Any] | None = None,
    scenario_payload: dict[str, Any] | None = None,
    *,
    retention_policy: RuntimeEventRetentionPolicy = DEFAULT_RUNTIME_EVENT_RETENTION_POLICY,
    persistence_policy: RuntimeEventPersistencePolicy = DEFAULT_RUNTIME_EVENT_PERSISTENCE_POLICY,
    generated_at_utc: str = "",
) -> dict[str, Any]:
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat()
    simulation = simulation_payload or {}
    scenario = _scenario_report(simulation, scenario_payload)
    recommended_backend = str(scenario.get("recommended_backend") or "NONE")
    blockers = [str(item) for item in scenario.get("governance_blockers") or ()]

    report = RuntimeEventPersistenceDryRunReport(
        report_id=_report_id(
            {
                "generated_at_utc": generated,
                "simulation_id": simulation.get("simulation_id"),
                "recommended_backend": recommended_backend,
            }
        ),
        generated_at_utc=generated,
        simulation_only=True,
        persistence_enabled=False,
        writes_performed=False,
        read_only=True,
        retention_policy_summary=_retention_policy_summary(retention_policy),
        persistence_approval_policy_summary=_persistence_policy_summary(
            persistence_policy,
        ),
        simulator_summary=_simulator_summary(simulation),
        backend_scenario_comparison=list(scenario.get("backend_comparison") or []),
        recommended_backend=recommended_backend,
        governance_blockers=blockers,
        safety_assertions=_safety_assertions(simulation, scenario),
        pcnrass_readiness_notes=_pcnrass_notes(simulation, blockers),
        remaining_approval_requirements=_remaining_approval_requirements(blockers),
        export_format="json",
    )
    return _json_safe_report(report.as_dict())


def _scenario_report(
    simulation: dict[str, Any],
    scenario_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    if scenario_payload:
        embedded = scenario_payload.get("scenario_report")
        if isinstance(embedded, dict):
            return embedded
        if str(scenario_payload.get("payload_version") or "").startswith(
            "css.runtime_event_persistence_scenario."
        ):
            return scenario_payload
    return build_runtime_event_persistence_scenario_report(simulation)


def _retention_policy_summary(policy: RuntimeEventRetentionPolicy) -> dict[str, Any]:
    return {
        "policy_version": policy.policy_version,
        "max_events": int(policy.max_events),
        "max_export_limit": int(policy.max_export_limit),
        "default_inspection_limit": int(policy.default_inspection_limit),
        "redaction_required": bool(policy.redaction_required),
        "allow_export": bool(policy.allow_export),
        "export_format": str(policy.export_format),
    }


def _persistence_policy_summary(policy: RuntimeEventPersistencePolicy) -> dict[str, Any]:
    return {
        "policy_version": policy.policy_version,
        "persistence_enabled": False,
        "operator_approval_required": bool(policy.operator_approval_required),
        "approval_token_required": bool(policy.approval_token_required),
        "approved_subsystems": list(policy.approved_subsystems),
        "max_persistence_window_minutes": int(policy.max_persistence_window_minutes),
        "allowed_export_formats": list(policy.allowed_export_formats),
        "redaction_required": bool(policy.redaction_required),
        "audit_logging_required": bool(policy.audit_logging_required),
    }


def _simulator_summary(simulation: dict[str, Any]) -> dict[str, Any]:
    return {
        "simulation_id": str(simulation.get("simulation_id") or ""),
        "accepted_events_count": _safe_int(simulation.get("accepted_events_count")),
        "rejected_events_count": _safe_int(simulation.get("rejected_events_count")),
        "redaction_failures_count": len(simulation.get("redaction_failures") or []),
        "estimated_storage_bytes": _safe_int(simulation.get("estimated_storage_bytes")),
        "estimated_event_rate": _safe_float(simulation.get("estimated_event_rate")),
        "inspected_events_count": _safe_int(simulation.get("inspected_events_count")),
        "truncated_events_count": _safe_int(simulation.get("truncated_events_count")),
        "persistence_enabled": False,
        "writes_performed": False,
        "simulation_only": True,
    }


def _safety_assertions(
    simulation: dict[str, Any],
    scenario: dict[str, Any],
) -> list[str]:
    assertions = [
        "PERSISTENCE_DISABLED",
        "REPORT_EXPORT_ONLY",
        "NO_RUNTIME_EVENT_WRITES",
        "NO_STORAGE_TABLES_CREATED",
        "NO_EXTERNAL_QUEUES_ENABLED",
        "NO_APPROVAL_GRANT_ENDPOINT",
        "NO_BROKER_OR_TRADING_BEHAVIOR_CHANGED",
        "JSON_SAFE_OUTPUT_ONLY",
    ]
    if simulation.get("writes_performed") is True:
        assertions.append("UNEXPECTED_WRITE_FLAG_REQUIRES_STOP")
    if scenario.get("persistence_enabled") is True:
        assertions.append("UNEXPECTED_PERSISTENCE_FLAG_REQUIRES_STOP")
    return assertions


def _pcnrass_notes(
    simulation: dict[str, Any],
    blockers: list[str],
) -> list[str]:
    notes = [
        "PCNRASS release check required before any future activation",
        "current report is suitable for dry-run review only",
    ]
    if blockers:
        notes.append("governance blockers remain before persistence approval")
    if _safe_int(simulation.get("rejected_events_count")):
        notes.append("simulation rejections must be resolved or formally accepted")
    if simulation.get("redaction_failures"):
        notes.append("redaction failures must be remediated before storage approval")
    return notes


def _remaining_approval_requirements(blockers: list[str]) -> list[str]:
    requirements = [
        "explicit operator approval",
        "approved storage backend",
        "approved retention window",
        "redaction review",
        "audit logging review",
        "PCNRASS release check",
    ]
    if "SIMULATION_REJECTIONS_REQUIRE_REVIEW" in blockers:
        requirements.append("simulation rejection review")
    if "REDACTION_FAILURES_REQUIRE_REMEDIATION" in blockers:
        requirements.append("redaction remediation")
    return list(dict.fromkeys(requirements))


def _json_safe_report(report: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(report, sort_keys=True, default=str))


def _report_id(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:20].upper()
    return f"EVREPORT-{digest}"


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
    "RUNTIME_EVENT_PERSISTENCE_REPORT_VERSION",
    "RuntimeEventPersistenceDryRunReport",
    "build_runtime_event_persistence_report",
]
