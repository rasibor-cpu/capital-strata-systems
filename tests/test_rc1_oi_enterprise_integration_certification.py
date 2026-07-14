from __future__ import annotations

import pytest

from backend.events.event_bus import EventBus
from backend.execution.unified_execution_pipeline import UnifiedExecutionPipeline, UnifiedExecutionPipelineError, UnifiedExecutionRequest
from backend.options.options_income_enterprise_adapter import ENTERPRISE_SAFE_FLAGS, OptionsIncomeEnterpriseIntegrationError, assert_enterprise_safe
from backend.options.options_income_rc1_certification import (
    build_live_disable_proof,
    build_production_readiness_contribution,
    build_rc1_oi_verdict,
    build_restart_replay_certification,
)
from backend.options.options_income_rc1_dashboard_registration import consume_rc1_oi_dashboard_host
from backend.options.options_income_rc1_event_audit_policy import build_rc1_oi_audit_policy, build_rc1_oi_event_policy
from backend.options.options_income_rc1_evidence import build_rc1_oi_evidence, evidence_hash
from backend.options.options_income_rc1_integration import MANDATORY_HOSTS, OptionsIncomeRC1IntegrationError, certify_options_income_rc1_integration, host_integration_health
from backend.options.options_income_rc1_runtime_snapshot import build_rc1_oi_runtime_snapshot, register_rc1_oi_runtime_snapshot
from backend.options.options_income_runtime_registration import SUBSYSTEM_ID, build_options_income_runtime_registration
from backend.options.options_income_certification import certify_options_income_engine
from backend.options.options_income_certification_adapter import adapt_options_income_certification
from backend.options.options_income_dashboard_adapter import build_options_income_enterprise_dashboard
from backend.options.options_income_rc1_report import build_rc1_oi_report
from backend.options.options_income_event_adapter import build_options_income_events
from backend.options.options_income_audit_adapter import OptionsIncomeAuditAdapter
from backend.options.options_income_enterprise_adapter import build_enterprise_operational_snapshot, build_enterprise_risk_contribution
from backend.options.options_income_alert_adapter import adapt_options_income_alerts
from backend.options.options_income_explainability_adapter import adapt_options_income_explanations
from backend.options.options_income_learning_adapter import build_options_income_learning_observations
from backend.derivatives.derivatives_exposure_service import build_options_income_derivatives_exposure
from backend.derivatives.derivatives_stress_service import build_options_income_derivatives_stress
from backend.derivatives.derivatives_volatility_service import build_options_income_derivatives_volatility


NOW = "2026-07-14T00:00:00+00:00"


@pytest.fixture()
def hosts() -> dict:
    return {
        "subsystem_registry": {},
        "runtime_snapshot_registry": {},
        "runtime_supervisor_registry": {},
        "dashboard_host": {},
        "event_bus": EventBus(),
        "audit_store": [],
        "certification_registry": {},
        "readiness_registry": {},
    }


@pytest.fixture(scope="module")
def oi010() -> dict:
    return certify_options_income_engine(timestamp=NOW, tests_executed=["rc1-oi"])


@pytest.fixture(scope="module")
def artifacts(oi010: dict) -> dict:
    return oi010["end_to_end"]["artifacts"]


def test_full_rc1_oi_certification_package(hosts: dict) -> None:
    result = certify_options_income_rc1_integration(hosts=hosts, timestamp=NOW, commit="abc123")
    assert result["verdict"]["final_verdict"] == "CERTIFIED_PAPER_INTEGRATION"
    assert result["verdict"]["implies_live_execution_readiness"] is False
    assert result["live_disable_proof"]["status"] == "PASS"
    assert result["restart_replay"]["status"] == "PASS"
    assert result["runtime_snapshot"]["subsystem_id"] == SUBSYSTEM_ID
    assert hosts["certification_registry"][SUBSYSTEM_ID] == result["verdict"]
    assert hosts["readiness_registry"][SUBSYSTEM_ID] == result["production_readiness"]
    assert all(result[key] is expected for key, expected in ENTERPRISE_SAFE_FLAGS.items())


def test_enterprise_subsystem_consumption_is_idempotent(hosts: dict) -> None:
    first = certify_options_income_rc1_integration(hosts=hosts, timestamp=NOW)
    second = certify_options_income_rc1_integration(hosts=hosts, timestamp=NOW)
    assert first["runtime_registration"] == second["runtime_registration"]
    assert first["runtime_snapshot"] == second["runtime_snapshot"]
    assert first["verdict"] == second["verdict"]
    assert len(hosts["audit_store"]) == 1


def test_duplicate_conflicting_subsystem_registration_fails_closed(hosts: dict) -> None:
    hosts["subsystem_registry"][SUBSYSTEM_ID] = {"subsystem_id": SUBSYSTEM_ID, "version": "CONFLICT", **ENTERPRISE_SAFE_FLAGS}
    with pytest.raises(Exception, match="duplicate subsystem registration"):
        certify_options_income_rc1_integration(hosts=hosts, timestamp=NOW)


def test_missing_mandatory_hosts_fail_closed(hosts: dict) -> None:
    for name in MANDATORY_HOSTS:
        broken = dict(hosts)
        broken[name] = None
        with pytest.raises(OptionsIncomeRC1IntegrationError, match="missing host integration contract"):
            certify_options_income_rc1_integration(hosts=broken, timestamp=NOW)


def test_runtime_snapshot_inclusion_and_registry_contract(artifacts: dict, oi010: dict) -> None:
    runtime = build_options_income_runtime_registration(timestamp=NOW, certification_status="PAPER_CERTIFIED")
    dashboard = build_options_income_enterprise_dashboard(artifacts["dashboard"], timestamp=NOW)
    risk = build_enterprise_risk_contribution(artifacts["risk"], portfolio=artifacts["portfolio"], timestamp=NOW)
    cert = adapt_options_income_certification(oi010, timestamp=NOW)
    op = build_enterprise_operational_snapshot(runtime_registration=runtime, dashboard=dashboard, risk=risk, certification=cert, timestamp=NOW)
    snapshot = build_rc1_oi_runtime_snapshot(runtime_registration=runtime, operational_snapshot=op, timestamp=NOW)
    registry = {}
    assert register_rc1_oi_runtime_snapshot(registry, snapshot) == snapshot
    assert snapshot["execution_allowed"] is False
    assert snapshot["data_freshness"]["status"] == "FRESH"


def test_runtime_snapshot_duplicate_conflict_fails_closed(artifacts: dict, oi010: dict) -> None:
    runtime = build_options_income_runtime_registration(timestamp=NOW)
    dashboard = build_options_income_enterprise_dashboard(artifacts["dashboard"], timestamp=NOW)
    cert = adapt_options_income_certification(oi010, timestamp=NOW)
    op = build_enterprise_operational_snapshot(runtime_registration=runtime, dashboard=dashboard, certification=cert, timestamp=NOW)
    snapshot = build_rc1_oi_runtime_snapshot(runtime_registration=runtime, operational_snapshot=op, timestamp=NOW)
    registry = {SUBSYSTEM_ID: {**snapshot, "health": "OFFLINE"}}
    with pytest.raises(OptionsIncomeEnterpriseIntegrationError, match="duplicate conflicting runtime snapshot"):
        register_rc1_oi_runtime_snapshot(registry, snapshot)


def test_dashboard_host_consumption_preserves_no_order_controls(artifacts: dict, oi010: dict) -> None:
    host = {}
    cert = adapt_options_income_certification(oi010, timestamp=NOW)
    runtime = build_options_income_runtime_registration(timestamp=NOW)
    payload = consume_rc1_oi_dashboard_host(host, dashboard_payload=artifacts["dashboard"], certification=cert, runtime_registration=runtime, timestamp=NOW)
    assert payload["order_entry_controls"] is False
    assert payload["trade_buttons"] is False
    assert "OPTIONS_INCOME" in host
    assert payload["enterprise_payload"]["sections"]["summary"]["mode"] == "PAPER"


def test_missing_dashboard_host_fails_closed(artifacts: dict) -> None:
    with pytest.raises(OptionsIncomeEnterpriseIntegrationError, match="missing dashboard host"):
        consume_rc1_oi_dashboard_host(None, dashboard_payload=artifacts["dashboard"], timestamp=NOW)


def test_event_and_audit_policy_idempotency_and_replay() -> None:
    delivered = []
    bus = EventBus()
    bus.subscribe("*", lambda event: delivered.append(event.event_id))
    rows = [
        {"event_type": "CERTIFICATION_COMPLETED", "entity_id": SUBSYSTEM_ID, "timestamp": NOW, "source_module": "m", "payload": {"ok": True}},
        {"event_type": "READINESS_UPDATED", "entity_id": SUBSYSTEM_ID, "timestamp": NOW, "source_module": "m", "payload": {"ok": True}},
    ]
    policy = build_rc1_oi_event_policy(rows, event_bus=bus)
    assert policy["status"] == "PASS"
    assert policy["idempotency_keys"] == delivered

    record = OptionsIncomeAuditAdapter().build_record(
        decision="RC1_OI",
        inputs={},
        outputs={"readiness_score": 100},
        rules_evaluated=["paper-only"],
        timestamp=NOW,
    )
    store = []
    first = build_rc1_oi_audit_policy([record], audit_store=store)
    second = build_rc1_oi_audit_policy([record], audit_store=store)
    assert first["idempotency_keys"] == second["idempotency_keys"]
    assert len(store) == 1


def test_sensitive_event_or_audit_fields_are_rejected() -> None:
    with pytest.raises(OptionsIncomeEnterpriseIntegrationError, match="sensitive field rejected"):
        build_rc1_oi_event_policy(
            [{"event_type": "CERTIFICATION_COMPLETED", "entity_id": "x", "timestamp": NOW, "source_module": "m", "payload": {"api_key": "SECRET"}}],
            event_bus=EventBus(),
        )
    record = OptionsIncomeAuditAdapter().build_record(
        decision="RC1_OI",
        inputs={},
        outputs={},
        rules_evaluated=[],
        timestamp=NOW,
    )
    record["private_key_path"] = "secret.pem"
    with pytest.raises(OptionsIncomeEnterpriseIntegrationError, match="sensitive field rejected"):
        build_rc1_oi_audit_policy([record], audit_store=[])


def test_rc1_evidence_mapping_and_hash_stability(hosts: dict) -> None:
    result = certify_options_income_rc1_integration(hosts=hosts, timestamp=NOW)
    evidence = result["certification_evidence"]
    assert evidence["overall_status"] == "PASS"
    assert {row["status"] for row in evidence["module_results"]} == {"PASS"}
    assert evidence_hash(evidence) == evidence_hash(dict(evidence))


def test_rc1_verdict_warning_fail_unavailable_and_failed_safety_states(hosts: dict) -> None:
    result = certify_options_income_rc1_integration(hosts=hosts, timestamp=NOW)
    evidence = dict(result["certification_evidence"])
    warning_rows = [dict(row) for row in evidence["module_results"]]
    warning_rows[0]["status"] = "WARNING"
    warning = {**evidence, "module_results": warning_rows, "warnings": ["architecture"]}
    assert build_rc1_oi_verdict(warning, timestamp=NOW)["final_verdict"] == "CERTIFIED_WITH_WARNINGS"

    fail_rows = [dict(row) for row in evidence["module_results"]]
    for row in fail_rows:
        if row["name"] == "runtime_snapshot":
            row["status"] = "FAIL"
    failed = {**evidence, "module_results": fail_rows, "failures": ["runtime_snapshot"]}
    assert build_rc1_oi_verdict(failed, timestamp=NOW)["final_verdict"] == "FAILED_SAFETY"
    assert build_rc1_oi_verdict({**evidence, "module_results": []}, timestamp=NOW)["final_verdict"] == "UNAVAILABLE"


def test_production_readiness_contribution(hosts: dict) -> None:
    result = certify_options_income_rc1_integration(hosts=hosts, timestamp=NOW)
    readiness = result["production_readiness"]
    assert readiness["readiness_state"] == "READY_FOR_RC1_INTEGRATION"
    assert readiness["production_deployed"] is False
    assert readiness["live_options_ready"] is False
    assert "production_deployment_certification" in readiness["remaining_prerequisites"]


def test_live_disable_proof_detects_order_and_secret_fields(hosts: dict) -> None:
    result = certify_options_income_rc1_integration(hosts=hosts, timestamp=NOW)
    proof = build_live_disable_proof(result["runtime_snapshot"], {"broker_ticket": "ABC", **ENTERPRISE_SAFE_FLAGS})
    assert proof["status"] == "FAIL"
    secret = build_live_disable_proof({"jwt": "SECRET", **ENTERPRISE_SAFE_FLAGS})
    assert secret["status"] == "FAIL"


def test_restart_replay_certification_deterministic(hosts: dict) -> None:
    result = certify_options_income_rc1_integration(hosts=hosts, timestamp=NOW)
    restart = build_restart_replay_certification(
        first_evidence=result["certification_evidence"],
        second_evidence=result["certification_evidence"],
        first_snapshot=result["runtime_snapshot"],
        second_snapshot=result["runtime_snapshot"],
    )
    assert restart["status"] == "PASS"
    drifted = build_restart_replay_certification(
        first_evidence=result["certification_evidence"],
        second_evidence={**result["certification_evidence"], "overall_score": 1},
        first_snapshot=result["runtime_snapshot"],
        second_snapshot=result["runtime_snapshot"],
    )
    assert drifted["status"] == "FAIL"


def test_host_integration_health(hosts: dict) -> None:
    health = host_integration_health(hosts)
    assert all(health[name] == "ONLINE" for name in ("runtime_host", "dashboard_host", "event_bus", "audit_framework", "certification_registry", "readiness_framework"))
    broken = dict(hosts)
    broken["event_bus"] = None
    assert host_integration_health(broken)["event_bus"] == "UNAVAILABLE"


def test_formal_rc1_report_idempotency(hosts: dict) -> None:
    result = certify_options_income_rc1_integration(hosts=hosts, timestamp=NOW, commit="abc123")
    report = result["report"]
    rebuilt = build_rc1_oi_report(
        commit="abc123",
        evidence=result["certification_evidence"],
        verdict=result["verdict"],
        production_readiness=result["production_readiness"],
        host_systems=sorted(MANDATORY_HOSTS),
        files_validated=["backend/options/options_income_rc1_integration.py", "backend/options/options_income_rc1_evidence.py", "backend/options/options_income_rc1_certification.py"],
        tests=["tests/test_rc1_oi_enterprise_integration_certification.py"],
        timestamp=NOW,
    )
    assert report == rebuilt
    assert report["paper_only_confirmation"] is True
    assert report["live_disable_confirmation"] is True


def test_shared_derivatives_services_available_and_failure(artifacts: dict) -> None:
    exposure = build_options_income_derivatives_exposure(artifacts["risk"], artifacts["portfolio"])
    stress = build_options_income_derivatives_stress(artifacts["dashboard"]["stress_tests"])
    volatility = build_options_income_derivatives_volatility(artifacts["risk"])
    assert exposure["asset_class"] == "OPTIONS"
    assert stress["paper_only"] is True
    assert volatility["advisory_only"] is True
    bad = dict(artifacts["risk"])
    bad["greeks_summary"] = {"portfolio": {"delta": float("nan")}}
    with pytest.raises(Exception, match="non-finite numeric value"):
        build_options_income_derivatives_exposure(bad, artifacts["portfolio"])


def test_oi_ei_integration_payloads_preserve_contracts(hosts: dict) -> None:
    result = certify_options_income_rc1_integration(hosts=hosts, timestamp=NOW)
    for section in (
        "runtime_registration",
        "runtime_snapshot",
        "dashboard_registration",
        "event_policy",
        "audit_policy",
        "certification_evidence",
        "verdict",
        "production_readiness",
        "live_disable_proof",
        "report",
    ):
        assert_enterprise_safe(result[section])


def test_unsafe_live_mode_execution_and_broker_armed_fail_closed() -> None:
    with pytest.raises(OptionsIncomeEnterpriseIntegrationError):
        assert_enterprise_safe({"mode": "LIVE", **ENTERPRISE_SAFE_FLAGS})
    with pytest.raises(OptionsIncomeEnterpriseIntegrationError):
        assert_enterprise_safe({"execution_allowed": True, "paper_only": True})
    with pytest.raises(OptionsIncomeEnterpriseIntegrationError):
        assert_enterprise_safe({"broker_execution_armed": True, "paper_only": True})


def test_unified_execution_regression_live_options_still_rejected() -> None:
    with pytest.raises(UnifiedExecutionPipelineError, match="Live mode rejected"):
        UnifiedExecutionPipeline().execute(UnifiedExecutionRequest(asset_class="OPTIONS", symbol="SPY", side="BUY", quantity=1, mode="live"))
