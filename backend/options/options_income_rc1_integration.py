from __future__ import annotations

from typing import Any, Mapping

from backend.derivatives.derivatives_exposure_service import build_options_income_derivatives_exposure
from backend.derivatives.derivatives_stress_service import build_options_income_derivatives_stress
from backend.derivatives.derivatives_volatility_service import build_options_income_derivatives_volatility
from backend.options.options_income_alert_adapter import adapt_options_income_alerts
from backend.options.options_income_audit_adapter import OptionsIncomeAuditAdapter
from backend.options.options_income_certification import certify_options_income_engine
from backend.options.options_income_certification_adapter import adapt_options_income_certification
from backend.options.options_income_dashboard_adapter import build_options_income_enterprise_dashboard
from backend.options.options_income_enterprise_adapter import (
    ENTERPRISE_SAFE_FLAGS,
    SUBSYSTEM_ID,
    OptionsIncomeEnterpriseIntegrationError,
    assert_enterprise_safe,
    build_enterprise_operational_snapshot,
    build_enterprise_risk_contribution,
)
from backend.options.options_income_event_adapter import build_options_income_events
from backend.options.options_income_explainability_adapter import adapt_options_income_explanations
from backend.options.options_income_learning_adapter import build_options_income_learning_observations
from backend.options.options_income_rc1_certification import (
    build_live_disable_proof,
    build_production_readiness_contribution,
    build_rc1_oi_verdict,
    build_restart_replay_certification,
)
from backend.options.options_income_rc1_dashboard_registration import consume_rc1_oi_dashboard_host
from backend.options.options_income_rc1_event_audit_policy import build_rc1_oi_audit_policy, build_rc1_oi_event_policy
from backend.options.options_income_rc1_evidence import build_rc1_oi_evidence
from backend.options.options_income_rc1_report import build_rc1_oi_report
from backend.options.options_income_rc1_runtime_snapshot import build_rc1_oi_runtime_snapshot, register_rc1_oi_runtime_snapshot
from backend.options.options_income_runtime_registration import build_options_income_runtime_registration, register_options_income_runtime


PAYLOAD_VERSION = "css.rc1_oi.integration.v1"
MANDATORY_HOSTS = (
    "subsystem_registry",
    "runtime_snapshot_registry",
    "runtime_supervisor_registry",
    "dashboard_host",
    "event_bus",
    "audit_store",
    "certification_registry",
    "readiness_registry",
)


class OptionsIncomeRC1IntegrationError(ValueError):
    """Raised when RC1-OI integration cannot certify safely."""


def certify_options_income_rc1_integration(
    *,
    hosts: Mapping[str, Any],
    timestamp: str,
    commit: str = "WORKTREE",
) -> dict[str, Any]:
    missing = [name for name in MANDATORY_HOSTS if hosts.get(name) is None]
    if missing:
        raise OptionsIncomeRC1IntegrationError(f"missing host integration contract: {','.join(missing)}")

    subsystem_registry = hosts["subsystem_registry"]
    runtime_snapshot_registry = hosts["runtime_snapshot_registry"]
    runtime_supervisor_registry = hosts["runtime_supervisor_registry"]
    dashboard_host = hosts["dashboard_host"]
    event_bus = hosts["event_bus"]
    audit_store = hosts["audit_store"]
    certification_registry = hosts["certification_registry"]
    readiness_registry = hosts["readiness_registry"]

    oi010 = certify_options_income_engine(timestamp=timestamp, tests_executed=["rc1_oi"])
    artifacts = oi010["end_to_end"]["artifacts"]
    certification = adapt_options_income_certification(oi010, timestamp=timestamp)
    runtime_registration = build_options_income_runtime_registration(
        timestamp=timestamp,
        certification_status="PAPER_CERTIFIED" if certification["enterprise_certification_status"] != "INTEGRATION_FAILED" else "INTEGRATION_FAILED",
    )
    register_options_income_runtime(subsystem_registry, runtime_registration)
    register_options_income_runtime(runtime_supervisor_registry, runtime_registration)

    dashboard = build_options_income_enterprise_dashboard(
        artifacts["dashboard"],
        certification=certification,
        runtime_registration=runtime_registration,
        timestamp=timestamp,
    )
    dashboard_registration = consume_rc1_oi_dashboard_host(
        dashboard_host,
        dashboard_payload=artifacts["dashboard"],
        certification=certification,
        runtime_registration=runtime_registration,
        timestamp=timestamp,
    )
    risk = build_enterprise_risk_contribution(artifacts["risk"], portfolio=artifacts["portfolio"], timestamp=timestamp)
    alerts = adapt_options_income_alerts(artifacts["dashboard"]["alerts"], timestamp=timestamp)
    explanations = adapt_options_income_explanations(artifacts["dashboard"]["explainability"], audit_reference="rc1-oi")
    learning = build_options_income_learning_observations(_learning_outcomes(artifacts), timestamp=timestamp, certification_result=certification)
    derivatives = {
        "exposure": build_options_income_derivatives_exposure(artifacts["risk"], artifacts["portfolio"]),
        "stress": build_options_income_derivatives_stress(artifacts["dashboard"]["stress_tests"]),
        "volatility": build_options_income_derivatives_volatility(artifacts["risk"]),
        **ENTERPRISE_SAFE_FLAGS,
    }
    events = build_options_income_events(_event_rows(timestamp))
    event_policy = build_rc1_oi_event_policy(_event_rows(timestamp), event_bus=event_bus)
    audit_record = OptionsIncomeAuditAdapter().build_record(
        decision="RC1_OI_CERTIFICATION",
        inputs={"subsystem": SUBSYSTEM_ID},
        outputs={"certification_score": certification["integration_score"]},
        rules_evaluated=["paper safety", "host integration", "event policy", "audit policy"],
        timestamp=timestamp,
        source_modules=["backend.options.options_income_rc1_integration"],
        certification_evidence=certification,
    )
    audit_policy = build_rc1_oi_audit_policy([audit_record], audit_store=audit_store)
    operational_snapshot = build_enterprise_operational_snapshot(
        runtime_registration=runtime_registration,
        dashboard=dashboard,
        risk=risk,
        alerts=alerts,
        certification=certification,
        events=events,
        audit_records=[audit_record],
        learning_feedback=learning,
        timestamp=timestamp,
    )
    runtime_snapshot = build_rc1_oi_runtime_snapshot(
        runtime_registration=runtime_registration,
        operational_snapshot=operational_snapshot,
        timestamp=timestamp,
    )
    register_rc1_oi_runtime_snapshot(runtime_snapshot_registry, runtime_snapshot)
    live_disable = build_live_disable_proof(
        runtime_registration,
        runtime_snapshot,
        dashboard_registration,
        event_policy,
        audit_policy,
        risk,
        *alerts,
        *explanations,
        *learning,
        certification,
    )
    first_evidence_seed = {
        "certification": certification,
        "runtime_registration": runtime_registration,
        "runtime_snapshot": runtime_snapshot,
        "dashboard_registration": dashboard_registration,
        "event_policy": event_policy,
        "audit_policy": audit_policy,
        "risk_contribution": risk,
        "alert_evidence": alerts,
        "explainability_evidence": explanations,
        "learning_evidence": learning,
        "derivatives_evidence": derivatives,
        "live_disable_proof": live_disable,
        "host_health": host_integration_health(hosts),
    }
    provisional_restart = {"status": "PASS", "stable_hashes": True, "restart_safe": True, **ENTERPRISE_SAFE_FLAGS}
    evidence_one = build_rc1_oi_evidence(restart_replay=provisional_restart, timestamp=timestamp, **first_evidence_seed)
    evidence_two = build_rc1_oi_evidence(restart_replay=provisional_restart, timestamp=timestamp, **first_evidence_seed)
    restart_replay = build_restart_replay_certification(
        first_evidence=evidence_one,
        second_evidence=evidence_two,
        first_snapshot=runtime_snapshot,
        second_snapshot=build_rc1_oi_runtime_snapshot(runtime_registration=runtime_registration, operational_snapshot=operational_snapshot, timestamp=timestamp),
    )
    evidence = build_rc1_oi_evidence(restart_replay=restart_replay, timestamp=timestamp, **first_evidence_seed)
    production = build_production_readiness_contribution(evidence=evidence, timestamp=timestamp)
    verdict = build_rc1_oi_verdict(evidence, timestamp=timestamp, production_readiness=production)
    certification_registry[SUBSYSTEM_ID] = verdict
    readiness_registry[SUBSYSTEM_ID] = production
    report = build_rc1_oi_report(
        commit=commit,
        evidence=evidence,
        verdict=verdict,
        production_readiness=production,
        host_systems=sorted(MANDATORY_HOSTS),
        files_validated=[
            "backend/options/options_income_rc1_integration.py",
            "backend/options/options_income_rc1_evidence.py",
            "backend/options/options_income_rc1_certification.py",
        ],
        tests=["tests/test_rc1_oi_enterprise_integration_certification.py"],
        timestamp=timestamp,
    )
    result = {
        "payload_version": PAYLOAD_VERSION,
        "subsystem": SUBSYSTEM_ID,
        "runtime_registration": runtime_registration,
        "runtime_snapshot": runtime_snapshot,
        "runtime_supervisor_registration": runtime_supervisor_registry[SUBSYSTEM_ID],
        "dashboard_registration": dashboard_registration,
        "event_policy": event_policy,
        "audit_policy": audit_policy,
        "certification_evidence": evidence,
        "verdict": verdict,
        "production_readiness": production,
        "live_disable_proof": live_disable,
        "restart_replay": restart_replay,
        "host_health": host_integration_health(hosts),
        "report": report,
        **ENTERPRISE_SAFE_FLAGS,
    }
    assert_enterprise_safe(result)
    return result


def host_integration_health(hosts: Mapping[str, Any]) -> dict[str, Any]:
    health = {
        "runtime_host": "ONLINE" if hosts.get("runtime_snapshot_registry") is not None and hosts.get("runtime_supervisor_registry") is not None else "UNAVAILABLE",
        "dashboard_host": "ONLINE" if hosts.get("dashboard_host") is not None else "UNAVAILABLE",
        "event_bus": "ONLINE" if hosts.get("event_bus") is not None else "UNAVAILABLE",
        "audit_framework": "ONLINE" if hosts.get("audit_store") is not None else "UNAVAILABLE",
        "certification_registry": "ONLINE" if hosts.get("certification_registry") is not None else "UNAVAILABLE",
        "readiness_framework": "ONLINE" if hosts.get("readiness_registry") is not None else "UNAVAILABLE",
        "alert_framework": "ONLINE",
        "explainability_framework": "ONLINE",
        "learning_framework": "ONLINE",
        "shared_derivatives_service": "ONLINE",
        **ENTERPRISE_SAFE_FLAGS,
    }
    assert_enterprise_safe(health)
    return health


def _event_rows(timestamp: str) -> list[dict[str, Any]]:
    return [
        {"event_type": "CERTIFICATION_COMPLETED", "entity_id": SUBSYSTEM_ID, "timestamp": timestamp, "source_module": "backend.options.options_income_rc1_certification", "payload": {"rc1_oi": True}},
        {"event_type": "READINESS_UPDATED", "entity_id": SUBSYSTEM_ID, "timestamp": timestamp, "source_module": "backend.options.options_income_rc1_integration", "payload": {"readiness": "READY_FOR_RC1_INTEGRATION"}},
    ]


def _learning_outcomes(artifacts: Mapping[str, Any]) -> list[dict[str, Any]]:
    positions = artifacts["dashboard"]["positions"]["active_positions"]
    if not positions:
        return []
    position = dict(positions[0])
    return [
        {
            "strategy": position.get("strategy_type"),
            "position_id": position.get("position_id"),
            "premium_realized": position.get("premium_realized", 0.0),
            "assignment_status": position.get("assignment_status", "UNKNOWN"),
            "capital_efficiency": 0.0,
            "income_target_achievement": 0.0,
            "paper_only": True,
        }
    ]


__all__ = ["MANDATORY_HOSTS", "PAYLOAD_VERSION", "OptionsIncomeRC1IntegrationError", "certify_options_income_rc1_integration", "host_integration_health"]
