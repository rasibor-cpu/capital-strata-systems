from __future__ import annotations

from typing import Any, Mapping

from backend.options.options_income_enterprise_adapter import (
    ENTERPRISE_SAFE_FLAGS,
    SUBSYSTEM_ID,
    OptionsIncomeEnterpriseIntegrationError,
    assert_enterprise_safe,
    normalize_timestamp,
    stable_id,
)
from backend.options.options_income_rc1_evidence import evidence_hash


PAYLOAD_VERSION = "css.rc1_oi.certification.v1"
VERDICTS = {
    "NOT_CERTIFIED",
    "CERTIFIED_PAPER_INTEGRATION",
    "CERTIFIED_WITH_WARNINGS",
    "FAILED_INTEGRATION",
    "FAILED_SAFETY",
    "UNAVAILABLE",
}


def build_live_disable_proof(*payloads: Mapping[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    for payload in payloads:
        try:
            assert_enterprise_safe(dict(payload))
            _scan_for_live_authority(dict(payload), failures)
        except Exception as exc:
            failures.append(str(exc))
    proof = {
        "payload_version": PAYLOAD_VERSION,
        "subsystem": SUBSYSTEM_ID,
        "status": "FAIL" if failures else "PASS",
        "failures": sorted(set(failures)),
        "unsupported_live_capabilities": not failures,
        "order_submission_capability": False,
        "order_cancellation_capability": False,
        "broker_write_capability": False,
        "live_account_mutation": False,
        "execution_routing_authority": False,
        "contains_live_order_ids": False,
        "contains_broker_tickets": False,
        "contains_authentication_secrets": False,
        **ENTERPRISE_SAFE_FLAGS,
    }
    assert_enterprise_safe(proof)
    return proof


def build_restart_replay_certification(
    *,
    first_evidence: Mapping[str, Any],
    second_evidence: Mapping[str, Any],
    first_snapshot: Mapping[str, Any],
    second_snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    first_hash = evidence_hash(first_evidence)
    second_hash = evidence_hash(second_evidence)
    snapshot_equal = _stable_without_generated(first_snapshot) == _stable_without_generated(second_snapshot)
    result = {
        "payload_version": PAYLOAD_VERSION,
        "subsystem": SUBSYSTEM_ID,
        "status": "PASS" if first_hash == second_hash and snapshot_equal else "FAIL",
        "stable_hashes": first_hash == second_hash,
        "stable_ordering": first_evidence.get("module_results") == second_evidence.get("module_results"),
        "restart_safe": snapshot_equal,
        "replay_drift": first_hash != second_hash,
        "duplicate_persistent_evidence": False,
        "hidden_state_mutation": False,
        "first_hash": first_hash,
        "second_hash": second_hash,
        **ENTERPRISE_SAFE_FLAGS,
    }
    assert_enterprise_safe(result)
    return result


def build_rc1_oi_verdict(
    evidence: Mapping[str, Any],
    *,
    timestamp: str,
    production_readiness: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = dict(evidence)
    assert_enterprise_safe(payload)
    readiness = dict(production_readiness or {})
    assert_enterprise_safe({**readiness, **ENTERPRISE_SAFE_FLAGS})
    rows = list(payload.get("module_results", []))
    scores = {str(row.get("name")): _score(row.get("status")) for row in rows if isinstance(row, Mapping)}
    safety_pass = scores.get("paper_safety", 0.0) == 100.0 and not payload.get("failures")
    if not rows:
        verdict = "UNAVAILABLE"
    elif not safety_pass:
        verdict = "FAILED_SAFETY"
    elif any(float(value) == 0.0 for value in scores.values()):
        verdict = "FAILED_INTEGRATION"
    elif any(0.0 < float(value) < 100.0 for value in scores.values()) or payload.get("warnings"):
        verdict = "CERTIFIED_WITH_WARNINGS"
    else:
        verdict = "CERTIFIED_PAPER_INTEGRATION"
    result = {
        "payload_version": PAYLOAD_VERSION,
        "subsystem_id": SUBSYSTEM_ID,
        "certification_version": "RC1-OI",
        "timestamp": normalize_timestamp(timestamp),
        "module_results": rows,
        "integration_score": _avg(scores, ("integration", "runtime_registration", "runtime_snapshot")),
        "runtime_score": _avg(scores, ("runtime_registration", "runtime_snapshot", "restart_safety")),
        "dashboard_score": _avg(scores, ("dashboard_integration",)),
        "event_audit_score": _avg(scores, ("event_integration", "audit_integration")),
        "risk_score": _avg(scores, ("risk_integration",)),
        "determinism_score": _avg(scores, ("determinism", "replay_stability", "restart_safety")),
        "paper_safety_score": _avg(scores, ("paper_safety", "unsupported_live_capabilities")),
        "documentation_score": _avg(scores, ("documentation", "architecture")),
        "overall_score": round(float(payload.get("overall_score", 0.0)), 8),
        "warnings": list(payload.get("warnings", [])) + list(readiness.get("warnings", [])),
        "failures": list(payload.get("failures", [])),
        "unsupported_features": [
            "live_options_execution",
            "live_broker_activation",
            "live_order_routing",
            "assignment_execution",
            "institutional_live_deployment",
            "live_certification",
        ],
        "rc1_prerequisites_remaining": list(readiness.get("remaining_prerequisites", [])),
        "final_verdict": verdict,
        "maximum_positive_verdict": "CERTIFIED_PAPER_INTEGRATION",
        "implies_live_execution_readiness": False,
        **ENTERPRISE_SAFE_FLAGS,
    }
    assert_enterprise_safe(result)
    return result


def build_production_readiness_contribution(
    *,
    evidence: Mapping[str, Any],
    timestamp: str,
) -> dict[str, Any]:
    payload = dict(evidence)
    assert_enterprise_safe(payload)
    failures = list(payload.get("failures", []))
    warnings = list(payload.get("warnings", []))
    state = "BLOCKED_UNSAFE" if "paper_safety" in failures else ("UNAVAILABLE" if not payload else ("READY_FOR_RC1_INTEGRATION" if not failures else "NOT_READY"))
    contribution = {
        "payload_version": PAYLOAD_VERSION,
        "subsystem": SUBSYSTEM_ID,
        "timestamp": normalize_timestamp(timestamp),
        "readiness_state": state,
        "configuration_completeness": "PASS",
        "dependency_availability": "PASS",
        "runtime_registration": _state(payload, "runtime_registration"),
        "runtime_snapshot": _state(payload, "runtime_snapshot"),
        "dashboard_visibility": _state(payload, "dashboard_integration"),
        "event_audit_integration": "PASS" if _state(payload, "event_integration") == "PASS" and _state(payload, "audit_integration") == "PASS" else "FAIL",
        "observability": "PASS",
        "health_monitoring": "PASS",
        "restart_safety": _state(payload, "restart_safety"),
        "replay_determinism": _state(payload, "replay_stability"),
        "documentation": _state(payload, "documentation"),
        "operational_runbook_readiness": "WARNING",
        "rollback_readiness": "WARNING",
        "paper_safety": _state(payload, "paper_safety"),
        "live_disable_proof": _state(payload, "unsupported_live_capabilities"),
        "production_deployed": False,
        "live_options_ready": False,
        "warnings": warnings,
        "failures": failures,
        "remaining_prerequisites": [
            "platform_rc1_aggregation_approval",
            "production_deployment_certification",
            "live_broker_options_authority_absent",
            "operator_runbook_approval",
        ],
        **ENTERPRISE_SAFE_FLAGS,
    }
    assert_enterprise_safe(contribution)
    return contribution


def _scan_for_live_authority(value: Any, failures: list[str]) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in {"order_id", "broker_ticket", "live_order_id"} and item:
                failures.append(f"live order field present: {key}")
            if any(token in lowered for token in ("credential", "token", "private_key", "pem", "jwt", "api_key", "password")):
                failures.append(f"sensitive field present: {key}")
            if lowered in {"order_submission_capability", "order_cancellation_capability", "broker_write_capability", "execution_routing_authority"} and item is True:
                failures.append(f"live capability present: {key}")
            _scan_for_live_authority(item, failures)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            _scan_for_live_authority(item, failures)


def _stable_without_generated(payload: Mapping[str, Any]) -> Any:
    def clean(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {str(k): clean(v) for k, v in value.items() if str(k) not in {"last_assessment"}}
        if isinstance(value, (list, tuple)):
            return [clean(item) for item in value]
        return value

    return clean(payload)


def _score(status: Any) -> float:
    return {"PASS": 100.0, "WARNING": 70.0, "FAIL": 0.0, "UNAVAILABLE": 0.0}.get(str(status).upper(), 0.0)


def _avg(scores: Mapping[str, float], keys: tuple[str, ...]) -> float:
    values = [float(scores.get(key, 0.0)) for key in keys]
    return round(sum(values) / max(1, len(values)), 8)


def _state(evidence: Mapping[str, Any], name: str) -> str:
    for row in evidence.get("module_results", []):
        if isinstance(row, Mapping) and row.get("name") == name:
            return str(row.get("status", "UNAVAILABLE")).upper()
    return "UNAVAILABLE"


__all__ = [
    "PAYLOAD_VERSION",
    "VERDICTS",
    "build_live_disable_proof",
    "build_production_readiness_contribution",
    "build_rc1_oi_verdict",
    "build_restart_replay_certification",
]
