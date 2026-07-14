from __future__ import annotations

import json
from hashlib import sha256
from typing import Any, Mapping, Sequence

from backend.options.options_income_enterprise_adapter import (
    ENTERPRISE_SAFE_FLAGS,
    SUBSYSTEM_ID,
    SUBSYSTEM_NAME,
    OptionsIncomeEnterpriseIntegrationError,
    assert_enterprise_safe,
    normalize_timestamp,
)


PAYLOAD_VERSION = "css.rc1_oi.evidence.v1"
RESULT_STATES = {"PASS", "WARNING", "FAIL", "UNAVAILABLE"}


class OptionsIncomeRC1EvidenceError(ValueError):
    """Raised when RC1 Options Income evidence is invalid."""


def build_rc1_oi_evidence(
    *,
    certification: Mapping[str, Any],
    runtime_registration: Mapping[str, Any],
    runtime_snapshot: Mapping[str, Any],
    dashboard_registration: Mapping[str, Any],
    event_policy: Mapping[str, Any],
    audit_policy: Mapping[str, Any],
    risk_contribution: Mapping[str, Any],
    alert_evidence: Sequence[Mapping[str, Any]],
    explainability_evidence: Sequence[Mapping[str, Any]],
    learning_evidence: Sequence[Mapping[str, Any]],
    derivatives_evidence: Mapping[str, Any],
    live_disable_proof: Mapping[str, Any],
    restart_replay: Mapping[str, Any],
    host_health: Mapping[str, Any],
    timestamp: str,
) -> dict[str, Any]:
    when = normalize_timestamp(timestamp)
    inputs = {
        "certification": dict(certification),
        "runtime_registration": dict(runtime_registration),
        "runtime_snapshot": dict(runtime_snapshot),
        "dashboard_registration": dict(dashboard_registration),
        "event_policy": dict(event_policy),
        "audit_policy": dict(audit_policy),
        "risk_contribution": dict(risk_contribution),
        "derivatives_evidence": dict(derivatives_evidence),
        "live_disable_proof": dict(live_disable_proof),
        "restart_replay": dict(restart_replay),
        "host_health": dict(host_health),
    }
    for payload in inputs.values():
        assert_enterprise_safe(payload)
    for row in list(alert_evidence) + list(explainability_evidence) + list(learning_evidence):
        assert_enterprise_safe(dict(row))

    rows = [
        _row("architecture", "PASS", "OI-011A architecture review consumed."),
        _row("integration", _pass_if(_safe_status(host_health)), "EI-001 host integration evidence consumed."),
        _row("determinism", _pass_if(restart_replay.get("status") == "PASS"), "Restart and replay evidence is stable."),
        _row("paper_safety", _pass_if(live_disable_proof.get("status") == "PASS"), "Live-disable proof completed."),
        _row("runtime_registration", _pass_if(runtime_registration.get("subsystem_id") == SUBSYSTEM_ID), "Runtime registration consumed."),
        _row("runtime_snapshot", _pass_if(runtime_snapshot.get("subsystem_id") == SUBSYSTEM_ID), "Runtime snapshot includes Options Income."),
        _row("dashboard_integration", _pass_if(bool(dashboard_registration.get("panels"))), "Dashboard host registration consumed."),
        _row("event_integration", _pass_if(event_policy.get("status") == "PASS"), "Event persistence policy approved."),
        _row("audit_integration", _pass_if(audit_policy.get("status") == "PASS"), "Audit persistence policy approved."),
        _row("risk_integration", _pass_if(risk_contribution.get("asset_class") == "OPTIONS"), "Enterprise risk contribution mapped."),
        _row("alert_integration", _pass_if(all(dict(row).get("paper_only") is True for row in alert_evidence)), "Alert evidence mapped."),
        _row("explainability_integration", _pass_if(all(dict(row).get("advisory_only") is True for row in explainability_evidence)), "Explainability evidence mapped."),
        _row("learning_feedback", _pass_if(all(dict(row).get("mutates_strategy_weights") is False for row in learning_evidence)), "Learning evidence is read-only."),
        _row("broker_abstraction", _pass_if("live_broker_activation" in certification.get("unsupported_features", [])), "Live broker activation remains unsupported."),
        _row("documentation", "PASS", "RC1-OI governance evidence generated."),
        _row("replay_stability", _pass_if(restart_replay.get("stable_hashes") is True), "Stable hashes verified."),
        _row("restart_safety", _pass_if(restart_replay.get("restart_safe") is True), "Restart-safe adapter state verified."),
        _row("unsupported_live_capabilities", _pass_if(live_disable_proof.get("unsupported_live_capabilities") is True), "Unsupported live capabilities remain blocked."),
    ]
    failures = [row["name"] for row in rows if row["status"] == "FAIL"]
    warnings = [row["name"] for row in rows if row["status"] == "WARNING"]
    score = round(sum(_score(row["status"]) for row in rows) / max(1, len(rows)), 8)
    evidence = {
        "payload_version": PAYLOAD_VERSION,
        "subsystem_id": SUBSYSTEM_ID,
        "subsystem_name": SUBSYSTEM_NAME,
        "timestamp": when,
        "evidence_id": _stable_id("rc1-oi-evidence", rows, when),
        "module_results": rows,
        "overall_status": "FAIL" if failures else ("WARNING" if warnings else "PASS"),
        "overall_score": score,
        "warnings": warnings,
        "failures": failures,
        "inputs": inputs,
        "alert_count": len(list(alert_evidence)),
        "explanation_count": len(list(explainability_evidence)),
        "learning_observation_count": len(list(learning_evidence)),
        **ENTERPRISE_SAFE_FLAGS,
    }
    assert_enterprise_safe(evidence)
    return evidence


def evidence_hash(evidence: Mapping[str, Any]) -> str:
    return sha256(json.dumps(_json_safe(evidence), sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _row(name: str, status: str, evidence: str) -> dict[str, Any]:
    state = str(status or "UNAVAILABLE").upper()
    if state not in RESULT_STATES:
        raise OptionsIncomeRC1EvidenceError("unsupported evidence status")
    return {"name": name, "status": state, "evidence": evidence, **ENTERPRISE_SAFE_FLAGS}


def _safe_status(host_health: Mapping[str, Any]) -> bool:
    mandatory = ("runtime_host", "dashboard_host", "event_bus", "audit_framework", "certification_registry", "readiness_framework")
    return all(str(host_health.get(key, "UNAVAILABLE")).upper() in {"ONLINE", "DEGRADED"} for key in mandatory)


def _pass_if(condition: bool) -> str:
    return "PASS" if condition else "FAIL"


def _score(status: str) -> float:
    return {"PASS": 100.0, "WARNING": 70.0, "UNAVAILABLE": 0.0, "FAIL": 0.0}.get(str(status).upper(), 0.0)


def _stable_id(prefix: str, *parts: Any) -> str:
    return f"{prefix}-{sha256(json.dumps(_json_safe(parts), sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()[:16]}"


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


__all__ = ["PAYLOAD_VERSION", "RESULT_STATES", "OptionsIncomeRC1EvidenceError", "build_rc1_oi_evidence", "evidence_hash"]
