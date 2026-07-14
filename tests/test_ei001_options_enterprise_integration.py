from __future__ import annotations

import pytest

from backend.derivatives.derivatives_exposure_service import build_options_income_derivatives_exposure
from backend.derivatives.derivatives_stress_service import build_options_income_derivatives_stress
from backend.derivatives.derivatives_volatility_service import build_options_income_derivatives_volatility
from backend.events.event_bus import EventBus
from backend.options.options_income_alert_adapter import adapt_options_income_alerts
from backend.options.options_income_audit_adapter import OptionsIncomeAuditAdapter
from backend.options.options_income_certification import certify_options_income_engine
from backend.options.options_income_certification_adapter import OptionsIncomeCertificationAdapter, adapt_options_income_certification
from backend.options.options_income_dashboard_adapter import (
    PANELS,
    build_options_income_enterprise_dashboard,
    register_options_income_dashboard,
)
from backend.options.options_income_end_to_end_validator import NOW
from backend.options.options_income_enterprise_adapter import (
    ENTERPRISE_SAFE_FLAGS,
    OptionsIncomeEnterpriseIntegrationError,
    assert_enterprise_safe,
    build_enterprise_operational_snapshot,
    build_enterprise_risk_contribution,
)
from backend.options.options_income_event_adapter import EVENT_TYPES, build_options_income_events, publish_options_income_events
from backend.options.options_income_explainability_adapter import adapt_options_income_explanations
from backend.options.options_income_learning_adapter import build_options_income_learning_observations
from backend.options.options_income_runtime_registration import (
    SUBSYSTEM_ID,
    build_options_income_runtime_registration,
    register_options_income_runtime,
)
from backend.execution.unified_execution_pipeline import UnifiedExecutionPipeline, UnifiedExecutionPipelineError, UnifiedExecutionRequest


@pytest.fixture(scope="module")
def certification() -> dict:
    return certify_options_income_engine(timestamp=NOW, tests_executed=["ei001"])


@pytest.fixture(scope="module")
def artifacts(certification: dict) -> dict:
    return certification["end_to_end"]["artifacts"]


def test_runtime_registration_is_safe_idempotent_and_non_executable() -> None:
    registration = build_options_income_runtime_registration(timestamp=NOW, certification_status="PAPER_CERTIFIED")
    assert registration["subsystem_id"] == SUBSYSTEM_ID
    assert registration["non_executable"] is True
    assert registration["capabilities"] == sorted(registration["capabilities"])
    assert all(registration[key] is expected for key, expected in ENTERPRISE_SAFE_FLAGS.items())

    registry = {}
    first = register_options_income_runtime(registry, registration)
    second = register_options_income_runtime(registry, registration)
    assert first == second
    assert list(registry) == [SUBSYSTEM_ID]


def test_duplicate_runtime_registration_fails_closed() -> None:
    registry = {}
    registration = build_options_income_runtime_registration(timestamp=NOW)
    register_options_income_runtime(registry, registration)
    conflicting = {**registration, "version": "CONFLICT"}
    with pytest.raises(OptionsIncomeEnterpriseIntegrationError, match="duplicate subsystem registration"):
        register_options_income_runtime(registry, conflicting)


def test_missing_runtime_registry_fails_closed() -> None:
    with pytest.raises(OptionsIncomeEnterpriseIntegrationError, match="missing enterprise registry"):
        register_options_income_runtime(None, build_options_income_runtime_registration(timestamp=NOW))


def test_event_publication_payload_shape_ordering_and_event_bus() -> None:
    rows = [
        {
            "event_type": "CERTIFICATION_COMPLETED",
            "entity_id": "cert",
            "timestamp": NOW,
            "source_module": "backend.options.options_income_certification",
            "payload": {"certification_status": "PASS"},
        },
        {
            "event_type": "OPPORTUNITY_ACCEPTED",
            "entity_id": "SPY-CALL",
            "timestamp": NOW,
            "source_module": "backend.options.options_income_opportunity_scanner",
            "payload": {"ranking_score": 92.0},
        },
    ]
    events = build_options_income_events(rows)
    assert [event["event_type"] for event in events] == ["OPPORTUNITY_ACCEPTED", "CERTIFICATION_COMPLETED"]
    assert events[0]["event_type"] in EVENT_TYPES
    assert all(event["execution_allowed"] is False for event in events)
    assert all(event["audit_metadata"]["append_only"] is True for event in events)

    bus = EventBus()
    delivered = []
    bus.subscribe("*", lambda event: delivered.append(event))
    published = publish_options_income_events(rows, bus)
    assert [event.event_id for event in delivered] == [item["event_id"] for item in published]


def test_event_idempotency_rejects_duplicate_event_ids() -> None:
    row = {
        "event_type": "ALERT_RAISED",
        "entity_id": "alert-1",
        "timestamp": NOW,
        "source_module": "backend.options.options_income_alerts",
        "payload": {"severity": "WARNING"},
    }
    with pytest.raises(OptionsIncomeEnterpriseIntegrationError, match="duplicate event IDs"):
        build_options_income_events([row, row])


def test_missing_event_bus_fails_closed() -> None:
    with pytest.raises(OptionsIncomeEnterpriseIntegrationError, match="missing event bus"):
        publish_options_income_events([], None)


def test_audit_adaptation_and_append_idempotency(certification: dict) -> None:
    adapter = OptionsIncomeAuditAdapter()
    record = adapter.build_record(
        decision="CERTIFICATION_COMPLETED",
        inputs={"scenario": "OI010"},
        outputs={"certification_score": certification["certification_score"]},
        rules_evaluated=["paper-only posture", "replay deterministic"],
        timestamp=NOW,
        source_modules=["backend.options.options_income_certification"],
        certification_evidence={"status": certification["certification_status"]},
    )
    store = []
    adapter.append(store, record)
    adapter.append(store, record)
    assert len(store) == 1
    assert store[0]["immutable"] is True
    assert store[0]["contains_sensitive_data"] is False


def test_missing_audit_framework_fails_closed(certification: dict) -> None:
    record = OptionsIncomeAuditAdapter().build_record(
        decision="CERTIFICATION_COMPLETED",
        inputs={},
        outputs={"certification_score": certification["certification_score"]},
        rules_evaluated=[],
        timestamp=NOW,
    )
    with pytest.raises(OptionsIncomeEnterpriseIntegrationError, match="missing audit framework"):
        OptionsIncomeAuditAdapter().append(None, record)


def test_dashboard_registration_and_payload_compatibility(artifacts: dict, certification: dict) -> None:
    registry = {}
    registration = register_options_income_dashboard(registry, payload_provider=lambda: artifacts["dashboard"])
    assert registration["read_only"] is True
    assert registry["OPTIONS_INCOME"]["panels"] == list(PANELS)

    payload = build_options_income_enterprise_dashboard(
        artifacts["dashboard"],
        certification=adapt_options_income_certification(certification, timestamp=NOW),
        runtime_registration=build_options_income_runtime_registration(timestamp=NOW),
        timestamp=NOW,
    )
    assert payload["sections"]["summary"]["mode"] == "PAPER"
    assert payload["sections"]["alerts"] == artifacts["dashboard"]["alerts"]
    assert payload["execution_allowed"] is False


def test_enterprise_risk_and_shared_derivatives_contributions(artifacts: dict) -> None:
    risk = artifacts["risk"]
    portfolio = artifacts["portfolio"]
    enterprise_risk = build_enterprise_risk_contribution(risk, portfolio=portfolio, timestamp=NOW)
    exposure = build_options_income_derivatives_exposure(risk, portfolio)
    stress = build_options_income_derivatives_stress(artifacts["dashboard"]["stress_tests"])
    volatility = build_options_income_derivatives_volatility(risk)

    assert enterprise_risk["asset_class"] == "OPTIONS"
    assert enterprise_risk["subsystem"] == "OPTIONS_INCOME"
    assert exposure["portfolio_delta"] == enterprise_risk["portfolio_delta"]
    assert stress["paper_only"] is True
    assert volatility["advisory_only"] is True


def test_invalid_derivatives_numeric_fails_closed(artifacts: dict) -> None:
    risk = dict(artifacts["risk"])
    risk["greeks_summary"] = {"portfolio": {"delta": float("nan")}}
    with pytest.raises(Exception, match="non-finite numeric value"):
        build_options_income_derivatives_exposure(risk, artifacts["portfolio"])


def test_alert_mapping_preserves_enterprise_severity_and_posture(artifacts: dict) -> None:
    alerts = adapt_options_income_alerts(artifacts["dashboard"]["alerts"], timestamp=NOW)
    assert alerts
    assert {alert["severity"] for alert in alerts} <= {"INFO", "WARNING", "CRITICAL"}
    assert all(alert["external_notification_sent"] is False for alert in alerts)
    assert all(alert["paper_only"] is True for alert in alerts)


def test_explainability_adaptation_is_audit_compatible(artifacts: dict) -> None:
    explanations = adapt_options_income_explanations(artifacts["dashboard"]["explainability"], audit_reference="audit-1")
    assert explanations
    assert all(row["audit_reference"] == "audit-1" for row in explanations)
    assert all(row["execution_allowed"] is False for row in explanations)


def test_learning_feedback_generation_prohibits_mutation(artifacts: dict, certification: dict) -> None:
    position = artifacts["dashboard"]["positions"]["active_positions"][0]
    observations = build_options_income_learning_observations(
        [
            {
                "strategy": position["strategy_type"],
                "position_id": position["position_id"],
                "premium_realized": position["premium_realized"],
                "assignment_status": position["assignment_status"],
                "capital_efficiency": 0.12,
                "income_target_achievement": 0.33,
                "paper_only": True,
            }
        ],
        timestamp=NOW,
        certification_result=certification,
    )
    assert observations[0]["mutates_strategy_weights"] is False
    assert observations[0]["mutates_execution_thresholds"] is False
    assert observations[0]["mutates_risk_limits"] is False
    assert observations[0]["mutates_broker_settings"] is False


def test_certification_registration_maps_oi010_evidence(certification: dict) -> None:
    adapted = adapt_options_income_certification(certification, timestamp=NOW)
    model = OptionsIncomeCertificationAdapter().readiness_model(certification)
    assert adapted["subsystem_id"] == "OPTIONS_INCOME"
    assert adapted["marks_platform_rc1_certified"] is False
    assert "live_options_execution" in adapted["unsupported_features"]
    assert model.details["execution_allowed"] is False


def test_operational_snapshot_combines_enterprise_state(artifacts: dict, certification: dict) -> None:
    runtime = build_options_income_runtime_registration(timestamp=NOW, certification_status="PAPER_CERTIFIED")
    dashboard = build_options_income_enterprise_dashboard(artifacts["dashboard"], timestamp=NOW)
    cert = adapt_options_income_certification(certification, timestamp=NOW)
    alerts = adapt_options_income_alerts(artifacts["dashboard"]["alerts"], timestamp=NOW)
    audit = [
        OptionsIncomeAuditAdapter().build_record(
            decision="READINESS_UPDATED",
            inputs={},
            outputs={"readiness_score": cert["integration_score"]},
            rules_evaluated=["certification evidence mapped"],
            timestamp=NOW,
        )
    ]
    learning = build_options_income_learning_observations([], timestamp=NOW)
    snapshot = build_enterprise_operational_snapshot(
        runtime_registration=runtime,
        dashboard=dashboard,
        risk=build_enterprise_risk_contribution(artifacts["risk"], portfolio=artifacts["portfolio"], timestamp=NOW),
        alerts=alerts,
        certification=cert,
        events=build_options_income_events(
            [
                {
                    "event_type": "READINESS_UPDATED",
                    "entity_id": "OPTIONS_INCOME",
                    "timestamp": NOW,
                    "source_module": "backend.options.options_income_runtime_registration",
                    "payload": {"readiness": "PAPER_CERTIFIED"},
                }
            ]
        ),
        audit_records=audit,
        learning_feedback=learning,
        timestamp=NOW,
    )
    assert snapshot["certification_state"] == "PAPER_CERTIFIED"
    assert snapshot["enterprise_integration_status"] in {"ONLINE", "DEGRADED"}
    assert snapshot["data_freshness"]["status"] == "FRESH"
    assert snapshot["execution_allowed"] is False


def test_unsafe_live_mode_and_execution_posture_fail_closed() -> None:
    with pytest.raises(OptionsIncomeEnterpriseIntegrationError, match="live mode is rejected"):
        assert_enterprise_safe({"mode": "LIVE", **ENTERPRISE_SAFE_FLAGS})
    with pytest.raises(OptionsIncomeEnterpriseIntegrationError, match="unsafe posture"):
        assert_enterprise_safe({"execution_allowed": True, "paper_only": True})
    with pytest.raises(OptionsIncomeEnterpriseIntegrationError, match="order-capable payload rejected"):
        assert_enterprise_safe({"place_order": {"symbol": "SPY"}, **ENTERPRISE_SAFE_FLAGS})
    with pytest.raises(OptionsIncomeEnterpriseIntegrationError, match="broker-write capability rejected"):
        assert_enterprise_safe({"broker_write_capable": True, **ENTERPRISE_SAFE_FLAGS})


def test_schema_versioning_and_stable_ordering() -> None:
    rows = [
        {"event_type": "STRESS_TEST_COMPLETED", "entity_id": "b", "timestamp": NOW, "source_module": "m", "payload": {}},
        {"event_type": "OPPORTUNITY_REJECTED", "entity_id": "a", "timestamp": NOW, "source_module": "m", "payload": {}},
    ]
    first = build_options_income_events(rows)
    second = build_options_income_events(list(reversed(rows)))
    assert [item["event_id"] for item in first] == [item["event_id"] for item in second]
    assert all(item["payload_version"].startswith("css.ei001.") for item in first)


def test_unified_execution_regression_live_options_still_rejected() -> None:
    pipeline = UnifiedExecutionPipeline()
    with pytest.raises(UnifiedExecutionPipelineError, match="Live mode rejected"):
        pipeline.execute(UnifiedExecutionRequest(asset_class="OPTIONS", symbol="SPY", side="BUY", quantity=1, mode="live"))
