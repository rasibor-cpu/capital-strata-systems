from __future__ import annotations

from typing import Any, Mapping, Sequence

from backend.options.options_income_enterprise_adapter import ENTERPRISE_SAFE_FLAGS, SUBSYSTEM_ID, assert_enterprise_safe, normalize_timestamp, stable_id


PAYLOAD_VERSION = "css.rc1_oi.report.v1"


def build_rc1_oi_report(
    *,
    commit: str,
    evidence: Mapping[str, Any],
    verdict: Mapping[str, Any],
    production_readiness: Mapping[str, Any],
    host_systems: Sequence[str],
    files_validated: Sequence[str],
    tests: Sequence[str],
    timestamp: str,
) -> dict[str, Any]:
    when = normalize_timestamp(timestamp)
    payloads = [dict(evidence), dict(verdict), dict(production_readiness)]
    for payload in payloads:
        assert_enterprise_safe(payload)
    report = {
        "payload_version": PAYLOAD_VERSION,
        "report_id": stable_id("rc1-oi-report", commit, evidence.get("evidence_id"), verdict.get("final_verdict"), when),
        "subsystem_id": SUBSYSTEM_ID,
        "commit": str(commit),
        "certification_timestamp": when,
        "architecture_reviewed": [
            "CSS_OPTIONS_INCOME_ENGINE_ARCHITECTURE_REVIEW.md",
            "PHASE_EI_001_OPTIONS_ENTERPRISE_INTEGRATION.md",
            "PHASE_OI_010_CONTROLLED_PAPER_CERTIFICATION.md",
            "CSS_OPTIONS_INCOME_ENGINE_COMPLETION_MATRIX.md",
        ],
        "host_systems_consumed": sorted(str(item) for item in host_systems),
        "files_modules_validated": sorted(str(item) for item in files_validated),
        "test_evidence": list(tests),
        "runtime_evidence": dict(evidence.get("inputs", {}).get("runtime_snapshot", {})),
        "dashboard_evidence": dict(evidence.get("inputs", {}).get("dashboard_registration", {})),
        "event_audit_evidence": {
            "event_policy": dict(evidence.get("inputs", {}).get("event_policy", {})),
            "audit_policy": dict(evidence.get("inputs", {}).get("audit_policy", {})),
        },
        "risk_evidence": dict(evidence.get("inputs", {}).get("risk_contribution", {})),
        "safety_evidence": dict(evidence.get("inputs", {}).get("live_disable_proof", {})),
        "restart_replay_evidence": dict(evidence.get("inputs", {}).get("restart_replay", {})),
        "readiness_evidence": dict(production_readiness),
        "warnings": list(verdict.get("warnings", [])),
        "failures": list(verdict.get("failures", [])),
        "known_limitations": [
            "full_platform_rc1_certification_not_granted",
            "production_deployment_certification_not_granted",
            "live_options_execution_not_available",
            "host_runtime_consumption_is_certified_through_adapter_contracts",
        ],
        "remaining_prerequisites": list(verdict.get("rc1_prerequisites_remaining", [])),
        "overall_score": verdict.get("overall_score", 0.0),
        "final_verdict": verdict.get("final_verdict", "UNAVAILABLE"),
        "paper_only_confirmation": True,
        "live_disable_confirmation": verdict.get("paper_safety_score", 0.0) == 100.0,
        **ENTERPRISE_SAFE_FLAGS,
    }
    assert_enterprise_safe(report)
    return report


__all__ = ["PAYLOAD_VERSION", "build_rc1_oi_report"]
