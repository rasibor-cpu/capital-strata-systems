from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from math import isfinite
from typing import Any

from dashboard.mission_control.approval_workflow import build_approval_workflow_console
from dashboard.mission_control.audit_console import build_audit_console
from dashboard.mission_control.broker_registry import build_broker_registry_console
from dashboard.mission_control.broker_telemetry import build_broker_telemetry
from dashboard.mission_control.capital_allocation import build_capital_allocation_center
from dashboard.mission_control.capital_committee import build_capital_committee_panel
from dashboard.mission_control.change_history import build_change_history_console
from dashboard.mission_control.committee_projection import build_committee_view
from dashboard.mission_control.configuration_console import build_configuration_console
from dashboard.mission_control.counterfactual_projection import build_counterfactual_projection
from dashboard.mission_control.decision_intelligence import build_decision_panel
from dashboard.mission_control.decision_trace import build_decision_trace
from dashboard.mission_control.evidence_graph import build_evidence_graph
from dashboard.mission_control.event_stream import build_alert_center, build_event_stream
from dashboard.mission_control.execution_committee import build_execution_committee_panel
from dashboard.mission_control.executive_dashboard import build_institutional_executive_dashboard
from dashboard.mission_control.explanation_projection import build_decision_explanation
from dashboard.mission_control.feature_flags import build_feature_flags_console
from dashboard.mission_control.final_certification import build_final_certification
from dashboard.mission_control.freshness import build_freshness_summary
from dashboard.mission_control.governance_summary import build_governance_summary_console
from dashboard.mission_control.health import build_health_summary
from dashboard.mission_control.institutional_reporting import build_institutional_reporting
from dashboard.mission_control.investment_committee import build_investment_committee_panel
from dashboard.mission_control.navigation import navigation_payload
from dashboard.mission_control.opportunity_ranking import build_opportunity_ranking
from dashboard.mission_control.operator_console import build_operator_console
from dashboard.mission_control.operations_timeline import build_operations_timeline
from dashboard.mission_control.performance_attribution import build_performance_attribution
from dashboard.mission_control.permissions import mission_control_permissions_payload, validate_read_only_permissions
from backend.security.vault_redaction import redact_value
from dashboard.mission_control.portfolio_projection import build_options_income_panel, build_performance_panel, build_portfolio_command_view
from dashboard.mission_control.profit_protection_projection import build_profit_protection_governance_projection
from dashboard.mission_control.recommendation_projection import build_recommendation_panel
from dashboard.mission_control.rbac_console import build_rbac_console
from dashboard.mission_control.risk_projection import build_risk_command_view
from dashboard.mission_control.risk_committee import build_risk_committee_panel
from dashboard.mission_control.rollback_console import build_rollback_console
from dashboard.mission_control.runtime_snapshot_normalizer import normalize_runtime_snapshot
from dashboard.mission_control.runtime_snapshot_provider import RuntimeSnapshotProvider
from dashboard.mission_control.safety import SAFE_FLAGS, mission_control_safety_payload, normalize_metric, validate_no_secret_payload
from dashboard.mission_control.serializers import state_hash, validate_serializable_payload
from dashboard.mission_control.source_registry import build_source_registry
from dashboard.mission_control.state_adapter import build_broker_registry, frontend_payload_from_runtime, section
from dashboard.mission_control.strategy_war_room import build_strategy_war_room
from dashboard.mission_control.system_metrics import build_executive_kpi_board, build_source_consistency, build_system_metrics
from dashboard.mission_control.trade_lifecycle import build_trade_lifecycle
from dashboard.runtime.frontend_contract import DATA_UNAVAILABLE
from backend.brokers.account_balance_contract import build_broker_balance_summary

_UNAVAILABLE_STATES = frozenset(
    {
        "UNAVAILABLE",
        "SOURCE_UNAVAILABLE",
        "DATA UNAVAILABLE",
        "DATA_UNAVAILABLE",
        "NOT_AVAILABLE",
    }
)


MISSION_CONTROL_SCHEMA_VERSION = "css.mission_control.state.v1"


@dataclass(frozen=True)
class MissionControlEnvelope:
    schema_version: str = MISSION_CONTROL_SCHEMA_VERSION
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = "dashboard.mission_control.contracts"
    advisory_only: bool = True
    read_only: bool = True


def build_mission_control_state(
    dashboard_state: Mapping[str, Any] | None = None,
    *,
    allow_mock: bool = True,
) -> dict[str, Any]:
    frontend = frontend_payload_from_runtime(dashboard_state, allow_mock=allow_mock)
    runtime_snapshot = _runtime_snapshot(dashboard_state, frontend)
    envelope = MissionControlEnvelope()
    sections = frontend.get("sections") if isinstance(frontend.get("sections"), Mapping) else {}
    account = section(frontend, "account_summary")
    broker = section(frontend, "broker")
    risk = section(frontend, "risk")
    market = section(frontend, "market")
    execution = section(frontend, "execution")
    positions = section(frontend, "positions")
    pnl = section(frontend, "pnl_summary")
    governance = section(frontend, "governance")
    certification = section(frontend, "runtime_certification_snapshot")
    alerts = _alerts(dashboard_state)
    credential_governance_source = (
        dashboard_state.get("credential_governance")
        if isinstance(dashboard_state, Mapping)
        and isinstance(dashboard_state.get("credential_governance"), Mapping)
        else {}
    )
    identity_governance_source = (
        dashboard_state.get("identity_governance")
        if isinstance(dashboard_state, Mapping)
        and isinstance(dashboard_state.get("identity_governance"), Mapping)
        else {}
    )
    oauth_governance_source = (
        dashboard_state.get("oauth_governance")
        if isinstance(dashboard_state, Mapping)
        and isinstance(dashboard_state.get("oauth_governance"), Mapping)
        else {}
    )
    enterprise_broker_runtime_source = (
        dashboard_state.get("enterprise_broker_runtime")
        if isinstance(dashboard_state, Mapping)
        and isinstance(dashboard_state.get("enterprise_broker_runtime"), Mapping)
        else {}
    )
    enterprise_governance_source = (
        dashboard_state.get("enterprise_governance")
        if isinstance(dashboard_state, Mapping)
        and isinstance(dashboard_state.get("enterprise_governance"), Mapping)
        else {}
    )
    production_readiness_source = (
        dashboard_state.get("production_readiness")
        if isinstance(dashboard_state, Mapping)
        and isinstance(dashboard_state.get("production_readiness"), Mapping)
        else {}
    )
    enterprise_broker_runtime_safe_source = _safe_enterprise_broker_runtime_source(
        enterprise_broker_runtime_source
    )
    safety = mission_control_safety_payload(
        {
            **SAFE_FLAGS,
            "broker": broker,
            "certification": certification,
            "mock_data": frontend.get("mission_control_mock_data"),
        }
    )
    profit_protection_source = _profit_protection_governance_source(
        dashboard_state,
        frontend,
        runtime_snapshot,
    )

    state = {
        **asdict(envelope),
        "navigation": navigation_payload(),
        "runtime_snapshot": runtime_snapshot,
        "platform": _platform(frontend, broker, certification, safety, runtime_snapshot),
        "runtime": _runtime(frontend, governance, certification, runtime_snapshot),
        "trading": _trading(execution, positions),
        "broker_balance_summary": (
            dict(account.get("broker_balance_summary"))
            if isinstance(account.get("broker_balance_summary"), Mapping)
            else build_broker_balance_summary(
                account,
                broker=str(account.get("broker") or broker.get("selected_broker") or "NONE"),
                mode=str(account.get("account_mode") or frontend.get("resolved_mode") or "ADVISORY"),
                as_of=str(frontend.get("generated_at") or ""),
            )
        ),
        "portfolio": _portfolio(account, positions, pnl, runtime_snapshot, frontend, execution),
        "market_intelligence": _market(market, runtime_snapshot),
        "risk": _risk(risk, governance, runtime_snapshot),
        "profit_protection_governance": build_profit_protection_governance_projection(
            profit_protection_source,
            generated_at=envelope.generated_at,
            runtime_source=str(runtime_snapshot.get("source") or frontend.get("mission_control_data_source") or DATA_UNAVAILABLE),
            runtime_state_hash=str(runtime_snapshot.get("state_hash") or DATA_UNAVAILABLE),
        ),
        "options_income": _options_income(sections),
        "brokers": _brokers(broker, runtime_snapshot),
        "alerts": _alerts_from_runtime(alerts, runtime_snapshot),
        "certification": _certification(certification, broker, runtime_snapshot),
        "audit": _audit(sections),
        "explainability": _explainability(sections),
        "learning": _learning(sections),
        "institutional_sources": _institutional_sources(sections),
        "governance": _governance(frontend, governance),
        "credential_governance": redact_value(
            {
                "schema_version": "css.credential.governance.v1",
                "vault_health": {"status": "UNCONFIGURED", "record_count": 0},
                "credential_inventory": [],
                "rotation_queue": [],
                "expiring_soon": [],
                "audit_events": [],
                "dependency_graph": {},
                "compliance": {"outcome": "EVIDENCE_PENDING"},
                "selected_credential": {},
                **dict(credential_governance_source),
                "secrets_returned": False,
                "advisory_only": True,
                "execution_allowed": False,
            }
        ),
        "identity_governance": redact_value(
            {
                "schema_version": "css.enterprise_identity.governance.v1",
                "enterprise_identity": [],
                "enterprise_secrets": [],
                "vault_health": {"status": "UNCONFIGURED", "record_count": 0},
                "rotation": {"reminders": [], "automatic_rotation": False},
                "certificates": [],
                "oauth": [],
                "broker_authentication": [],
                "risk": {"high_risk_count": 0},
                "audit": [],
                "secret_authority": {},
                "legacy_compatibility": [],
                "ownership_coverage": {"coverage_pct": 0},
                "orphaned_secrets": [],
                "direct_access_violations": [],
                "migration_progress": {"complete": False},
                "vault_health_score": {"score": 0, "status": "UNCONFIGURED"},
                **dict(identity_governance_source),
                "plaintext_returned": False,
                "advisory_only": True,
                "execution_allowed": False,
            }
        ),
        "oauth_governance": redact_value(
            {
                "schema_version": "css.oauth.governance.v1",
                "provider_inventory": [],
                "authorization_status": [],
                "scope_summary": {},
                "expiry_forecast": [],
                "rotation_readiness": {"rows": []},
                "risk": {"high_risk_count": 0},
                "policy": {},
                "audit": [],
                "certification": {"outcome": "NOT_CERTIFIED"},
                **dict(oauth_governance_source),
                "authorization_performed": False,
                "refresh_performed": False,
                "execution_allowed": False,
            }
        ),
        "enterprise_broker_runtime": redact_value(
            {
                "schema_version": "css.enterprise_broker_runtime.governance.v1",
                "broker_health": {"status": "CONFIGURATION_REQUIRED", "bindings": []},
                "oauth_status": [],
                "lease_health": _safe_lease_health(enterprise_broker_runtime_safe_source),
                "credential_governance_summary": {
                    "enterprise_binding_count": 0,
                    "legacy_compatibility_count": 0,
                    "plaintext_returned": False,
                },
                "provider_health": {},
                "holdings_readiness": {},
                "market_data_readiness": [],
                "options_readiness": [],
                "advisory_readiness": "DATA_DEPENDENCY_BLOCKED",
                "certification": {"outcome": "NOT_CERTIFIED"},
                **dict(enterprise_broker_runtime_safe_source),
                "execution_posture": "DISABLED",
                "execution_authority": "BLOCKED",
                "fail_closed": True,
                "advisory_only": True,
                "execution_allowed": False,
            }
        ),
        "enterprise_governance": redact_value(
            {
                "schema_version": "css.enterprise_governance.v1",
                "overall_certification_readiness": 0,
                "governance_score": 0,
                "domains": {},
                "iso_27001": {"percentage": 0, "formal_certification_claimed": False},
                "iso_9001": {"percentage": 0, "formal_certification_claimed": False},
                "business_continuity": {"percentage": 0},
                "enterprise_risk_summary": {"risk_count": 0},
                "enterprise_risk_register": [],
                "certification": {
                    "status": "EVIDENCE_INCOMPLETE",
                    "formal_certification_claimed": False,
                },
                "broker_readiness": "EVIDENCE_MISSING",
                "runtime_readiness": "EVIDENCE_MISSING",
                "security_posture": "EVIDENCE_MISSING",
                "compliance_posture": "EVIDENCE_MISSING",
                "outstanding_blockers": [],
                **dict(enterprise_governance_source),
                "formal_certification_claimed": False,
                "production_certified": False,
                "read_only": True,
                "execution_posture": "DISABLED",
                "execution_authority": "BLOCKED",
                "fail_closed": True,
                "advisory_only": True,
                "execution_allowed": False,
            }
        ),
        "production_readiness": redact_value(
            {
                "schema_version": "css.production_readiness.certification.v1",
                "status": "NOT_CERTIFIED",
                "certification_score": 0,
                "governance_score": 0,
                "broker_readiness": "EVIDENCE_MISSING",
                "runtime_readiness": "EVIDENCE_MISSING",
                "deployment_blockers": [],
                "outstanding_risks": {},
                "evidence_completeness": 0,
                "platform_certification": {},
                "operational_acceptance": {},
                "endurance_readiness": {},
                "disaster_recovery_readiness": {},
                "deployment_readiness": {},
                **dict(production_readiness_source),
                "evidence_fabricated": False,
                "deployment_authorized": False,
                "deployment_performed": False,
                "production_trading_certified": False,
                "execution_posture": "DISABLED",
                "execution_authority": "BLOCKED",
                "fail_closed": True,
                "advisory_only": True,
                "execution_allowed": False,
            }
        ),
        "configuration": _configuration(frontend, broker, sections),
        "documentation": _documentation_index(),
        "permissions": mission_control_permissions_payload(),
        "safety": safety,
        "mock_data": bool(frontend.get("mission_control_mock_data")),
        "mock_data_label": "MOCK DATA - NOT LIVE" if frontend.get("mission_control_mock_data") else "RUNTIME DATA",
    }
    state["operations_timeline"] = build_operations_timeline(state)
    state["event_stream"] = build_event_stream(state)
    state["trade_lifecycle"] = build_trade_lifecycle(state)
    state["portfolio_command"] = build_portfolio_command_view(state)
    state["broker_telemetry"] = build_broker_telemetry(state)
    state["risk_command_center"] = build_risk_command_view(state)
    state["alert_center"] = build_alert_center(state)
    state["executive_kpis"] = build_executive_kpi_board(state)
    state["performance_panel"] = build_performance_panel(state)
    state["options_income_panel"] = build_options_income_panel(state)
    state["system_metrics"] = build_system_metrics(state)
    state["decision_panel"] = build_decision_panel(state)
    state["decision_trace"] = build_decision_trace(state)
    state["decision_explanation"] = build_decision_explanation(state)
    state["committee_view"] = build_committee_view(state)
    state["counterfactuals"] = build_counterfactual_projection(state)
    state["recommendation_panel"] = build_recommendation_panel(state)
    state["evidence_graph"] = build_evidence_graph(state)
    state["strategy_war_room"] = build_strategy_war_room(state)
    state["opportunity_ranking"] = build_opportunity_ranking(state)
    state["capital_allocation_center"] = build_capital_allocation_center(state)
    state["performance_attribution"] = build_performance_attribution(state)
    state["investment_committee"] = build_investment_committee_panel(state)
    state["risk_committee"] = build_risk_committee_panel(state)
    state["execution_committee"] = build_execution_committee_panel(state)
    state["capital_committee"] = build_capital_committee_panel(state)
    state["institutional_executive_dashboard"] = build_institutional_executive_dashboard(state)
    state["institutional_reporting"] = build_institutional_reporting(state)
    state["rbac_console"] = build_rbac_console(state)
    state["operator_console"] = build_operator_console(state)
    state["approval_workflow_console"] = build_approval_workflow_console(state)
    state["configuration_console"] = build_configuration_console(state)
    state["broker_registry_console"] = build_broker_registry_console(state)
    state["feature_flags_console"] = build_feature_flags_console(state)
    state["audit_console"] = build_audit_console(state)
    state["change_history_console"] = build_change_history_console(state)
    state["rollback_console"] = build_rollback_console(state)
    state["governance_summary_console"] = build_governance_summary_console(state)
    state["source_consistency"] = build_source_consistency(state)
    source_registry = build_source_registry(
        frontend,
        state,
        dashboard_state_available=bool(frontend.get("mission_control_dashboard_state_available")),
        allow_mock=allow_mock,
    )
    _align_runtime_source_registry(source_registry, state)
    freshness = build_freshness_summary(source_registry)
    state["source_registry"] = source_registry
    state["data_sources"] = source_registry
    state["freshness"] = freshness
    state["data_freshness"] = _data_freshness(frontend, broker, certification, freshness, runtime_snapshot)
    state["health"] = build_health_summary(state, freshness_summary=freshness)
    state["state_hash"] = state_hash({key: value for key, value in state.items() if key not in {"generated_at", "state_hash"}})
    validation = validate_mission_control_state(state)
    state["contract_validation"] = validation
    if not validation["valid"]:
        state["platform"]["platform_status"] = "FAIL_CLOSED"
        state["safety"]["fail_closed"] = True
        state["safety"]["safety_status"] = "FAIL_CLOSED"
        state["health"] = build_health_summary(state, freshness_summary=freshness)
    state["final_certification"] = build_final_certification(state)
    return _json_safe(state)


def validate_mission_control_state(state: Mapping[str, Any] | None) -> dict[str, Any]:
    source = state if isinstance(state, Mapping) else {}
    reasons: list[str] = []
    if source.get("schema_version") != MISSION_CONTROL_SCHEMA_VERSION:
        reasons.append("invalid_schema_version")
    safety = source.get("safety") if isinstance(source.get("safety"), Mapping) else {}
    for key, expected in SAFE_FLAGS.items():
        if safety.get(key) is not expected:
            reasons.append(f"safety_flag_invalid:{key}")
    if not isinstance(source.get("navigation"), list) or len(source.get("navigation", [])) != 16:
        reasons.append("navigation_structure_invalid")
    permissions_ok, permission_reasons = validate_read_only_permissions(
        source.get("permissions") if isinstance(source.get("permissions"), Mapping) else {}
    )
    if not permissions_ok:
        reasons.extend(permission_reasons)
    ok, secret_reasons = validate_no_secret_payload(source)
    if not ok:
        reasons.extend(secret_reasons)
    serialization = validate_serializable_payload(source)
    if not serialization["valid"]:
        reasons.extend(serialization["reasons"])
    _scan_non_finite(source, reasons=reasons)
    source_consistency = source.get("source_consistency") if isinstance(source.get("source_consistency"), Mapping) else {}
    if source_consistency.get("status") == "FAIL_CLOSED":
        reasons.append("source_consistency_failed")
    if source_consistency.get("demo_runtime_mixing") is True:
        reasons.append("demo_runtime_mixing")
    committee_view = source.get("committee_view") if isinstance(source.get("committee_view"), Mapping) else {}
    if committee_view.get("status") == "FAIL_CLOSED":
        reasons.append("committee_outcomes_contradictory")
    evidence_graph = source.get("evidence_graph") if isinstance(source.get("evidence_graph"), Mapping) else {}
    if evidence_graph.get("status") == "FAIL_CLOSED":
        reasons.append("evidence_graph_inconsistent")
    recommendation_panel = source.get("recommendation_panel") if isinstance(source.get("recommendation_panel"), Mapping) else {}
    if recommendation_panel.get("forbidden_terms_absent") is False:
        reasons.append("recommendation_contains_execution_language")
    runtime_snapshot = source.get("runtime_snapshot") if isinstance(source.get("runtime_snapshot"), Mapping) else {}
    if (
        source.get("mock_data") is not True
        and str(runtime_snapshot.get("runtime_status", "")).upper() in {"OFFLINE", "UNAVAILABLE"}
    ):
        reasons.append("runtime_evidence_unavailable")
    for panel_name in (
        "strategy_war_room",
        "opportunity_ranking",
        "capital_allocation_center",
        "performance_attribution",
        "investment_committee",
        "risk_committee",
        "execution_committee",
        "capital_committee",
        "institutional_executive_dashboard",
        "institutional_reporting",
        "rbac_console",
        "operator_console",
        "approval_workflow_console",
        "configuration_console",
        "broker_registry_console",
        "feature_flags_console",
        "audit_console",
        "change_history_console",
        "rollback_console",
        "governance_summary_console",
    ):
        panel = source.get(panel_name) if isinstance(source.get(panel_name), Mapping) else {}
        if str(panel.get("status", "")).lower() == "fail_closed" and not _panel_preserves_read_only_safety(panel):
            reasons.append(f"unsafe_fail_closed_panel:{panel_name}")
    return {
        "valid": not reasons,
        "status": "PASS" if not reasons else "FAIL_CLOSED",
        "reasons": sorted(set(reasons)),
        **SAFE_FLAGS,
        "advisory_only": True,
    }


def mission_control_state_json(state: Mapping[str, Any], *, indent: int | None = None) -> str:
    return json.dumps(_json_safe(dict(state)), sort_keys=True, separators=None if indent else (",", ":"), indent=indent, default=str)


def _runtime_snapshot(dashboard_state: Any, frontend: Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(dashboard_state, Mapping) and isinstance(dashboard_state.get("runtime_snapshot"), Mapping):
        return dict(dashboard_state["runtime_snapshot"])
    source = dashboard_state if isinstance(dashboard_state, Mapping) else {"frontend_payload": dict(frontend)}
    provider = RuntimeSnapshotProvider(lambda: source)
    return provider.get_snapshot()


def _platform(frontend: Mapping[str, Any], broker: Mapping[str, Any], certification: Mapping[str, Any], safety: Mapping[str, Any], runtime_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    runtime_broker = runtime_snapshot.get("broker") if isinstance(runtime_snapshot.get("broker"), Mapping) else {}
    selected_broker = "UNAVAILABLE" if _runtime_unavailable(runtime_snapshot) else runtime_broker.get("selected_broker", broker.get("selected_broker", "UNAVAILABLE"))
    broker_health = "UNAVAILABLE" if _runtime_unavailable(runtime_snapshot) else runtime_broker.get("broker_health", broker.get("broker_health", "UNAVAILABLE"))
    return {
        "product": "CSS Mission Control",
        "platform_status": _first_status(runtime_snapshot.get("runtime_health"), certification.get("certification"), runtime_broker.get("broker_health"), "UNAVAILABLE"),
        "runtime_health": runtime_snapshot.get("runtime_health", "UNAVAILABLE"),
        "runtime_mode": runtime_snapshot.get("runtime_mode")
        or frontend.get("runtime_mode")
        or frontend.get("resolved_mode")
        or "DISABLED",
        "engine_mode": runtime_snapshot.get("engine_mode", "UNAVAILABLE"),
        "cycle": (
            (frontend.get("sections") or {}).get("runtime_telemetry", {}).get("display_cycle")
            if isinstance(frontend.get("sections"), Mapping)
            and isinstance((frontend.get("sections") or {}).get("runtime_telemetry"), Mapping)
            and (frontend.get("sections") or {}).get("runtime_telemetry", {}).get("display_cycle")
            not in (None, "", "UNKNOWN", "NOT_REPORTED", "UNAVAILABLE")
            else runtime_snapshot.get("cycle", "UNAVAILABLE")
        ),
        "heartbeat": runtime_snapshot.get("last_heartbeat", "UNAVAILABLE"),
        "selected_broker": selected_broker,
        "broker_health": broker_health,
        "risk_state": (runtime_snapshot.get("risk") or {}).get("risk_status", "UNAVAILABLE") if isinstance(runtime_snapshot.get("risk"), Mapping) else "UNAVAILABLE",
        "active_alerts": (runtime_snapshot.get("alerts") or {}).get("count", "UNAVAILABLE") if isinstance(runtime_snapshot.get("alerts"), Mapping) else "UNAVAILABLE",
        "execution_authority": "BLOCKED" if not safety.get("execution_allowed") else "UNKNOWN",
        "live_trading_blocked": True,
        "last_refresh": frontend.get("generated_at", DATA_UNAVAILABLE),
        "runtime_offline": runtime_snapshot.get("runtime_status") in {"OFFLINE", "UNAVAILABLE"},
    }


def _runtime(frontend: Mapping[str, Any], governance: Mapping[str, Any], certification: Mapping[str, Any], runtime_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    session = frontend.get("session") if isinstance(frontend.get("session"), Mapping) else {}
    active_runtime_sources = {"RUNTIME", "LIVE", "RUNTIME_ENDPOINT", "RUNTIME_ARTIFACT", "RUNTIME_REGISTRY"}
    sections = frontend.get("sections") if isinstance(frontend.get("sections"), Mapping) else {}
    telemetry = sections.get("runtime_telemetry") if isinstance(sections.get("runtime_telemetry"), Mapping) else {}
    platform = sections.get("runtime_status") if isinstance(sections.get("runtime_status"), Mapping) else {}
    # Prefer canonical telemetry; never invent cycle 0 from missing session fields.
    display_cycle = telemetry.get("display_cycle")
    if display_cycle in (None, "", "UNKNOWN", "NOT_REPORTED", "UNAVAILABLE"):
        if "cycle" in runtime_snapshot and runtime_snapshot.get("cycle") is not None:
            display_cycle = runtime_snapshot.get("cycle")
        elif "cycle_number" in session and session.get("cycle_number") is not None:
            display_cycle = session.get("cycle_number")
        else:
            display_cycle = DATA_UNAVAILABLE
    restart = telemetry.get("managed_service_restart_count")
    if restart in (None, "", "UNKNOWN", "NOT_REPORTED", "UNAVAILABLE"):
        restart = runtime_snapshot.get("restart_count", DATA_UNAVAILABLE)
    source_contract = _runtime_source_contract(frontend, runtime_snapshot)
    return {
        "runtime_id": runtime_snapshot.get("runtime_id", DATA_UNAVAILABLE),
        "runtime_status": runtime_snapshot.get("runtime_status", certification.get("operational_state", DATA_UNAVAILABLE)),
        "runtime_mode": platform.get("runtime_mode")
        or runtime_snapshot.get("runtime_mode")
        or frontend.get("resolved_mode", DATA_UNAVAILABLE),
        "engine_mode": platform.get("engine_mode")
        or runtime_snapshot.get("engine_mode", session.get("engine_mode", DATA_UNAVAILABLE)),
        "broker_mode": platform.get("broker_mode", DATA_UNAVAILABLE),
        "mobile_access_mode": platform.get("mobile_access_mode", DATA_UNAVAILABLE),
        "execution_state": platform.get("execution_state", "BLOCKED"),
        "cycle_mode": runtime_snapshot.get("cycle_mode", DATA_UNAVAILABLE),
        "cycle": display_cycle,
        "session_cycle": telemetry.get("session_cycle", DATA_UNAVAILABLE),
        "supervisor_cycles_completed": telemetry.get("supervisor_cycles_completed", DATA_UNAVAILABLE),
        "display_cycle": telemetry.get("display_cycle", display_cycle),
        "uptime": telemetry.get("uptime_seconds", runtime_snapshot.get("uptime_seconds", DATA_UNAVAILABLE)),
        "heartbeat": telemetry.get("heartbeat", runtime_snapshot.get("last_heartbeat", frontend.get("generated_at", DATA_UNAVAILABLE))),
        "heartbeat_status": runtime_snapshot.get("heartbeat_status", telemetry.get("freshness", DATA_UNAVAILABLE)),
        "heartbeat_age_seconds": telemetry.get("heartbeat_age_seconds", runtime_snapshot.get("heartbeat_age_seconds", DATA_UNAVAILABLE)),
        "last_successful_cycle": runtime_snapshot.get("last_successful_cycle", DATA_UNAVAILABLE),
        "last_failed_cycle": runtime_snapshot.get("last_failed_cycle", DATA_UNAVAILABLE),
        "supervisor_state": telemetry.get("supervisor_status", runtime_snapshot.get("runtime_status", DATA_UNAVAILABLE)),
        "restart_count": restart,
        "managed_service_restart_count": telemetry.get("managed_service_restart_count", restart),
        "failure_count": telemetry.get("supervisor_failure_count", runtime_snapshot.get("failure_count", DATA_UNAVAILABLE)),
        "recovery_count": telemetry.get("recovery_attempts", runtime_snapshot.get("recovery_count", DATA_UNAVAILABLE)),
        "alert_count": runtime_snapshot.get("alert_count", DATA_UNAVAILABLE),
        "disconnect_count": telemetry.get("broker_disconnect_count", runtime_snapshot.get("disconnect_count", DATA_UNAVAILABLE)),
        "state_hash": telemetry.get("state_hash", runtime_snapshot.get("state_hash", DATA_UNAVAILABLE)),
        "source": source_contract["source"],
        "selected_source": source_contract["selected_source"],
        "authoritative_source": source_contract["authoritative_source"],
        "fallback_source": source_contract["fallback_source"],
        "available_sources": source_contract["available_sources"],
        "source_freshness": source_contract["source_freshness"],
        "source_confidence": source_contract["source_confidence"],
        "source_status": source_contract["source_status"],
        "source_disagreement": source_contract["source_disagreement"],
        "source_diagnostics": source_contract["source_diagnostics"],
        "telemetry_provenance": telemetry.get("provenance", {}),
        "subsystem_health": {
            "audit": governance.get("audit_enabled", DATA_UNAVAILABLE),
            "api": "AVAILABLE" if runtime_snapshot.get("source") in active_runtime_sources else DATA_UNAVAILABLE,
            "dashboard": "AVAILABLE",
            "mobile": "AVAILABLE" if runtime_snapshot.get("source") in active_runtime_sources else DATA_UNAVAILABLE,
            "certification": certification.get("certification", DATA_UNAVAILABLE),
        },
        "controls": {"restart": "DISABLED_MC001", "shutdown": "DISABLED_MC001"},
    }


def _runtime_source_contract(frontend: Mapping[str, Any], runtime_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    diagnostics = runtime_snapshot.get("source_diagnostics") if isinstance(runtime_snapshot.get("source_diagnostics"), Mapping) else {}
    mock = bool(frontend.get("mission_control_mock_data")) or (
        isinstance(frontend.get("session"), Mapping)
        and bool(frontend.get("session", {}).get("mock_data"))
    )
    snapshot_source = _source_label(runtime_snapshot.get("source"))
    selected_source = _source_label(diagnostics.get("selected_source") or snapshot_source)
    if mock:
        selected_source = "MOCK"
        snapshot_source = "MOCK"
    authoritative_source = selected_source if selected_source not in {"", "UNKNOWN", "UNAVAILABLE"} else snapshot_source
    available_sources = []
    candidates = diagnostics.get("candidate_sources")
    if isinstance(candidates, list):
        for candidate in candidates:
            if isinstance(candidate, Mapping) and candidate.get("available"):
                source_type = _source_label(candidate.get("source_type"))
                if source_type not in available_sources:
                    available_sources.append(source_type)
    if authoritative_source not in {"", "UNKNOWN", "UNAVAILABLE"} and authoritative_source not in available_sources:
        available_sources.append(authoritative_source)
    source_freshness = _source_label(
        diagnostics.get("selected_freshness_status")
        or runtime_snapshot.get("data_freshness")
        or runtime_snapshot.get("heartbeat_status")
        or "UNAVAILABLE"
    )
    disagreement = (
        snapshot_source not in {"", "UNKNOWN", "UNAVAILABLE"}
        and selected_source not in {"", "UNKNOWN", "UNAVAILABLE"}
        and snapshot_source != selected_source
    )
    stale = source_freshness in {"STALE", "RED", "EXPIRED"}
    unavailable = authoritative_source in {"", "UNKNOWN", "UNAVAILABLE"}
    if unavailable:
        source_status = "RED"
        confidence = "NONE"
    elif disagreement or stale:
        source_status = "AMBER"
        confidence = "LOW" if stale else "MEDIUM"
    else:
        source_status = "GREEN" if source_freshness in {"FRESH", "GREEN"} else "AMBER"
        confidence = "HIGH" if source_status == "GREEN" else "MEDIUM"
    return {
        "source": authoritative_source or "UNAVAILABLE",
        "selected_source": selected_source or "UNAVAILABLE",
        "authoritative_source": authoritative_source or "UNAVAILABLE",
        "fallback_source": _source_label(diagnostics.get("fallback") or ""),
        "available_sources": available_sources,
        "source_freshness": source_freshness,
        "source_confidence": confidence,
        "source_status": source_status,
        "source_disagreement": disagreement,
        "source_diagnostics": dict(diagnostics),
    }


def _source_label(value: Any) -> str:
    return str(value or "UNAVAILABLE").strip().upper()


def _align_runtime_source_registry(source_registry: dict[str, dict[str, Any]], state: Mapping[str, Any]) -> None:
    runtime = state.get("runtime") if isinstance(state.get("runtime"), Mapping) else {}
    runtime_snapshot = state.get("runtime_snapshot") if isinstance(state.get("runtime_snapshot"), Mapping) else {}
    runtime_source = _source_label(runtime.get("source") or runtime_snapshot.get("source"))
    if runtime_source in {"", "UNKNOWN", "UNAVAILABLE"}:
        return
    for section in ("runtime", "runtime_snapshot"):
        descriptor = source_registry.get(section)
        if isinstance(descriptor, dict):
            descriptor["source"] = runtime_source
            provenance = descriptor.get("provenance") if isinstance(descriptor.get("provenance"), Mapping) else {}
            descriptor["provenance"] = {
                **dict(provenance),
                "canonical_runtime_source": runtime_source,
                "source_contract": "dashboard.mission_control.contracts.runtime_source_contract",
            }


def _trading(execution: Mapping[str, Any], positions: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "candidate_trades": [],
        "accepted_decisions": execution.get("accepted_trades", execution.get("accepted_trade_count", 0)),
        "rejected_decisions": execution.get("rejected_trades", execution.get("rejected_trade_count", 0)),
        "trade_gate_outcomes": [],
        "execution_status": execution.get("execution_state", DATA_UNAVAILABLE),
        "paper_positions": positions.get("open_positions", []),
        "open_positions": positions.get("open_positions", []),
        "closed_positions": positions.get("closed_positions", []),
        "orders": [],
        "fills": [],
        "rejections": [],
        "slippage": execution.get("avg_slippage", DATA_UNAVAILABLE),
        "fees": execution.get("fee_cost", DATA_UNAVAILABLE),
        "execution_quality": execution.get("execution_cost_state", DATA_UNAVAILABLE),
        "read_only": True,
    }


def _portfolio(
    account: Mapping[str, Any],
    positions: Mapping[str, Any],
    pnl: Mapping[str, Any],
    runtime_snapshot: Mapping[str, Any],
    frontend: Mapping[str, Any] | None = None,
    execution: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    runtime_portfolio = runtime_snapshot.get("portfolio") if isinstance(runtime_snapshot.get("portfolio"), Mapping) else {}
    if _runtime_unavailable(runtime_snapshot):
        runtime_portfolio = {}
    execution_payload = execution if isinstance(execution, Mapping) else {}
    frontend_payload = frontend if isinstance(frontend, Mapping) else {}
    cash = _honest_metric(
        account.get("cash_balance"),
        runtime_portfolio.get("cash"),
        availability=_field_availability(account, "cash_balance", runtime_portfolio.get("cash_availability")),
    )
    equity = _honest_metric(
        account.get("total_equity"),
        runtime_portfolio.get("equity"),
        availability=_field_availability(account, "total_equity", runtime_portfolio.get("equity_availability")),
    )
    buying_power = _honest_metric(
        account.get("buying_power"),
        runtime_portfolio.get("buying_power"),
        availability=_field_availability(account, "buying_power", runtime_portfolio.get("buying_power_availability")),
    )
    available_free = _honest_metric(
        account.get("available_margin"),
        account.get("available_balance"),
        buying_power if buying_power != "UNAVAILABLE" else None,
        availability=account.get("available_margin_availability")
        or account.get("buying_power_availability")
        or ("AVAILABLE" if buying_power != "UNAVAILABLE" else "UNAVAILABLE"),
    )
    realized = _honest_metric(
        pnl.get("realized_pnl"),
        runtime_portfolio.get("realized_pnl"),
        availability=_field_availability(pnl, "realized_pnl", runtime_portfolio.get("realized_pnl_availability")),
    )
    unrealized = _honest_metric(
        pnl.get("unrealized_pnl"),
        runtime_portfolio.get("unrealized_pnl"),
        availability=_field_availability(pnl, "unrealized_pnl", runtime_portfolio.get("unrealized_pnl_availability")),
    )
    net_pnl = _honest_metric(
        pnl.get("net_pnl"),
        runtime_portfolio.get("net_pnl"),
        availability=_field_availability(pnl, "net_pnl", runtime_portfolio.get("net_pnl_availability")),
    )
    open_count = _honest_metric(
        positions.get("total"),
        positions.get("open_count"),
        runtime_portfolio.get("open_positions"),
        availability=_field_availability(
            positions,
            "total",
            positions.get("open_count_availability"),
            runtime_portfolio.get("open_positions_availability"),
        ),
    )
    holdings = runtime_portfolio.get("positions") or positions.get("items") or positions.get("open_positions") or []
    if not isinstance(holdings, list):
        holdings = []
    if _unavailable_token(positions.get("total_availability") or positions.get("open_count_availability")):
        holdings = []
    source = str(
        account.get("source")
        or pnl.get("source")
        or positions.get("source")
        or runtime_snapshot.get("source")
        or DATA_UNAVAILABLE
    )
    return {
        "equity": equity,
        "cash": cash,
        "buying_power": buying_power,
        "available_free": available_free,
        "portfolio_value": equity,
        "session_pnl": net_pnl,
        "total_exposure": _honest_metric(
            runtime_portfolio.get("exposure"),
            positions.get("total_exposure"),
            pnl.get("total_exposure"),
            availability=pnl.get("total_exposure_availability"),
        ),
        "capital_deployed": _honest_metric(
            runtime_portfolio.get("capital_deployed"),
            positions.get("total_exposure"),
        ),
        "capital_available": available_free if available_free != "UNAVAILABLE" else buying_power,
        "realized_pnl": realized,
        "unrealized_pnl": unrealized,
        "net_pnl": net_pnl,
        "open_positions": open_count,
        "positions": holdings,
        "session_pnl_by_instrument": "UNAVAILABLE",
        "holdings": holdings if holdings else "UNAVAILABLE",
        "liquidity_margin": {
            "cash": cash,
            "available_free": available_free,
            "buying_power": buying_power,
            "margin_used": _honest_metric(
                account.get("margin_used"),
                availability=account.get("margin_used_availability"),
            ),
            "available_margin": _honest_metric(
                account.get("available_margin"),
                availability=account.get("available_margin_availability"),
            ),
            "source": source,
        },
        "maturity_expiry": {
            "status": "UNAVAILABLE",
            "profile": "UNAVAILABLE",
            "next_maturity": "UNAVAILABLE",
            "source": "UNAVAILABLE",
        },
        "execution_status": execution_payload.get("execution_state", DATA_UNAVAILABLE),
        "operating_context": {
            "runtime_mode": frontend_payload.get("resolved_mode") or runtime_snapshot.get("runtime_mode") or DATA_UNAVAILABLE,
            "advisory_only": True,
            "read_only": True,
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
            "source": source,
        },
        "asset_allocation": runtime_portfolio.get("asset_allocation", positions.get("asset_counts", {})),
        "sector_allocation": DATA_UNAVAILABLE,
        "currency_exposure": account.get("currency") or "UNAVAILABLE",
        "pnl_by_asset_class": "UNAVAILABLE"
        if _unavailable_token(pnl.get("availability_state"))
        else runtime_portfolio.get("pnl_by_asset", pnl.get("asset_unrealized_pnl", {})),
        "pnl_by_strategy": DATA_UNAVAILABLE,
        "collateral_utilization": _honest_metric(
            account.get("margin_used"),
            availability=account.get("margin_used_availability"),
        ),
        "capital_efficiency": DATA_UNAVAILABLE,
        "drawdown": _honest_metric(runtime_portfolio.get("drawdown")),
        "performance_attribution": DATA_UNAVAILABLE,
        "cash_availability": account.get("cash_balance_availability", "UNAVAILABLE" if cash == "UNAVAILABLE" else "AVAILABLE"),
        "equity_availability": account.get("total_equity_availability", "UNAVAILABLE" if equity == "UNAVAILABLE" else "AVAILABLE"),
        "buying_power_availability": account.get("buying_power_availability", "UNAVAILABLE" if buying_power == "UNAVAILABLE" else "AVAILABLE"),
        "realized_pnl_availability": pnl.get("realized_pnl_availability", "UNAVAILABLE" if realized == "UNAVAILABLE" else "AVAILABLE"),
        "unrealized_pnl_availability": pnl.get("unrealized_pnl_availability", "UNAVAILABLE" if unrealized == "UNAVAILABLE" else "AVAILABLE"),
        "net_pnl_availability": pnl.get("net_pnl_availability", "UNAVAILABLE" if net_pnl == "UNAVAILABLE" else "AVAILABLE"),
        "open_positions_availability": positions.get("total_availability")
        or positions.get("open_count_availability")
        or ("UNAVAILABLE" if open_count == "UNAVAILABLE" else "AVAILABLE"),
        "source": source,
        "availability_state": account.get("availability_state") or pnl.get("availability_state") or "UNAVAILABLE",
    }


def _unavailable_token(value: Any) -> bool:
    return str(value or "").strip().upper().replace(" ", "_") in {
        token.replace(" ", "_") for token in _UNAVAILABLE_STATES
    }


def _field_availability(payload: Mapping[str, Any], field: str, *fallbacks: Any) -> Any:
    explicit = payload.get(f"{field}_availability")
    if explicit not in (None, ""):
        return explicit
    for fallback in fallbacks:
        if fallback not in (None, ""):
            return fallback
    return None


def _honest_metric(*values: Any, availability: Any = None) -> Any:
    if _unavailable_token(availability):
        return "UNAVAILABLE"
    for value in values:
        if value in (None, "", DATA_UNAVAILABLE, "UNAVAILABLE"):
            continue
        if availability is None and _unavailable_token(value):
            continue
        return normalize_metric(value)
    return "UNAVAILABLE"


def _market(market: Mapping[str, Any], runtime_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    runtime_market = runtime_snapshot.get("market") if isinstance(runtime_snapshot.get("market"), Mapping) else {}
    if _runtime_unavailable(runtime_snapshot):
        return {
            "market_regime": DATA_UNAVAILABLE,
            "trend": DATA_UNAVAILABLE,
            "volatility": DATA_UNAVAILABLE,
            "liquidity": DATA_UNAVAILABLE,
            "momentum": DATA_UNAVAILABLE,
            "pressure": DATA_UNAVAILABLE,
            "probability": DATA_UNAVAILABLE,
            "velocity": DATA_UNAVAILABLE,
            "vwap_state": DATA_UNAVAILABLE,
            "spread_quality": DATA_UNAVAILABLE,
            "execution_cost_state": DATA_UNAVAILABLE,
            "signal_confluence": DATA_UNAVAILABLE,
            "asset_class_rankings": [],
            "watchlists": [],
            "market_data_freshness": DATA_UNAVAILABLE,
        }
    return {
        "market_regime": runtime_market.get("market_regime", market.get("market_regime", market.get("regime_state", DATA_UNAVAILABLE))),
        "trend": runtime_market.get("trend", market.get("trend_state", DATA_UNAVAILABLE)),
        "volatility": runtime_market.get("volatility", market.get("volatility_state", DATA_UNAVAILABLE)),
        "liquidity": runtime_market.get("liquidity", market.get("liquidity_state", DATA_UNAVAILABLE)),
        "momentum": runtime_market.get("momentum", market.get("momentum_state", DATA_UNAVAILABLE)),
        "pressure": market.get("pressure_state", DATA_UNAVAILABLE),
        "probability": market.get("probability_state", DATA_UNAVAILABLE),
        "velocity": market.get("velocity_state", DATA_UNAVAILABLE),
        "vwap_state": runtime_market.get("vwap", market.get("vwap_state", DATA_UNAVAILABLE)),
        "spread_quality": runtime_market.get("spread", market.get("spread_state", DATA_UNAVAILABLE)),
        "execution_cost_state": market.get("execution_cost_state", DATA_UNAVAILABLE),
        "signal_confluence": runtime_market.get("signal_confluence", market.get("signal_confluence_state", DATA_UNAVAILABLE)),
        "asset_class_rankings": [],
        "watchlists": [],
        "market_data_freshness": market.get("market_data_freshness", DATA_UNAVAILABLE),
    }


def _risk(risk: Mapping[str, Any], governance: Mapping[str, Any], runtime_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    runtime_risk = runtime_snapshot.get("risk") if isinstance(runtime_snapshot.get("risk"), Mapping) else {}
    if _runtime_unavailable(runtime_snapshot):
        return {
            "overall_risk_state": DATA_UNAVAILABLE,
            "risk_score": DATA_UNAVAILABLE,
            "trade_gate_status": DATA_UNAVAILABLE,
            "limit_breaches": [],
            "warnings": [],
            "drawdown": DATA_UNAVAILABLE,
            "exposure": DATA_UNAVAILABLE,
            "concentration": DATA_UNAVAILABLE,
            "liquidity_risk": DATA_UNAVAILABLE,
            "volatility_risk": DATA_UNAVAILABLE,
            "greeks": DATA_UNAVAILABLE,
            "stress_tests": DATA_UNAVAILABLE,
            "assignment_exposure": DATA_UNAVAILABLE,
            "collateral_utilization": DATA_UNAVAILABLE,
            "capital_limits": DATA_UNAVAILABLE,
            "daily_session_loss_limits": DATA_UNAVAILABLE,
            "anti_bleed_guard": DATA_UNAVAILABLE,
            "unified_trade_gate": DATA_UNAVAILABLE,
            "margin_gate": DATA_UNAVAILABLE,
            "kill_switch": DATA_UNAVAILABLE,
        }
    return {
        "overall_risk_state": runtime_risk.get("risk_status", risk.get("risk_state", DATA_UNAVAILABLE)),
        "risk_score": runtime_risk.get("risk_score", risk.get("risk_score", DATA_UNAVAILABLE)),
        "trade_gate_status": runtime_risk.get("trade_gate_status", risk.get("gate_status", DATA_UNAVAILABLE)),
        "limit_breaches": risk.get("limit_breaches", []),
        "warnings": risk.get("warnings", []),
        "drawdown": normalize_metric(runtime_risk.get("drawdown", risk.get("current_drawdown"))),
        "exposure": normalize_metric(runtime_risk.get("exposure", risk.get("total_exposure"))),
        "concentration": DATA_UNAVAILABLE,
        "liquidity_risk": DATA_UNAVAILABLE,
        "volatility_risk": DATA_UNAVAILABLE,
        "greeks": DATA_UNAVAILABLE,
        "stress_tests": DATA_UNAVAILABLE,
        "assignment_exposure": DATA_UNAVAILABLE,
        "collateral_utilization": DATA_UNAVAILABLE,
        "capital_limits": DATA_UNAVAILABLE,
        "daily_session_loss_limits": DATA_UNAVAILABLE,
        "anti_bleed_guard": runtime_risk.get("anti_bleed_guard", governance.get("anti_bleed_guard", DATA_UNAVAILABLE)),
        "unified_trade_gate": governance.get("unified_trade_gate", DATA_UNAVAILABLE),
        "margin_gate": runtime_risk.get("margin_gate", governance.get("margin_gate", DATA_UNAVAILABLE)),
        "kill_switch": runtime_risk.get("kill_switch", governance.get("kill_switch", DATA_UNAVAILABLE)),
    }


def _options_income(sections: Mapping[str, Any]) -> dict[str, Any]:
    options = sections.get("options_income") if isinstance(sections.get("options_income"), Mapping) else {}
    status = str(options.get("status") or "").strip()
    # Phase 177D: when frontend has not published OI, serve canonical runtime aggregation
    if not options or status in {"", "UNAVAILABLE", "NOT YET DEPLOYED"}:
        try:
            from backend.options.options_income_runtime_service import build_mission_control_options_income

            return build_mission_control_options_income()
        except Exception as exc:  # noqa: BLE001 — fail-closed MC projection
            return {
                "status": "FAILED",
                "deployment_state": "NOT_DEPLOYED",
                "opportunities": [],
                "accepted_candidates": [],
                "rejected_candidates": [],
                "covered_calls": [],
                "cash_secured_puts": [],
                "paper_positions": [],
                "premium_accounting": {"status": "FAILED", "reason": type(exc).__name__},
                "collateral": {"status": "FAILED"},
                "position_health": "FAILED",
                "rolling_recommendations": [],
                "income_targets": {"status": "FAILED"},
                "portfolio_allocation": {},
                "greeks": {"status": "FAILED"},
                "assignment_risk": {"status": "FAILED"},
                "volatility_risk": {"status": "FAILED"},
                "stress_tests": {},
                "alerts": [],
                "certification": {"outcome": "FAILED"},
                "operational_readiness": "FAILED",
                "data_source": "RUNTIME",
                "execution_blocked": True,
                "advisory_only": True,
                "failure_reason": type(exc).__name__,
            }
    return {
        "status": options.get("status", "UNAVAILABLE"),
        "engine_status": options.get("engine_status", options.get("status", "UNAVAILABLE")),
        "deployment_state": options.get("deployment_state", "DEPLOYED"),
        "opportunities": options.get("opportunities", []),
        "accepted_candidates": options.get("accepted_candidates", []),
        "rejected_candidates": options.get("rejected_candidates", []),
        "covered_calls": options.get("covered_calls", []),
        "cash_secured_puts": options.get("cash_secured_puts", []),
        "paper_positions": options.get("paper_positions", []),
        "premium_accounting": options.get("premium_accounting", "UNAVAILABLE"),
        "collateral": options.get("collateral", "UNAVAILABLE"),
        "position_health": options.get("position_health", "UNAVAILABLE"),
        "rolling_recommendations": options.get("rolling_recommendations", []),
        "income_targets": options.get("income_targets", "UNAVAILABLE"),
        "run_rate": options.get("run_rate", options.get("income_targets", "UNAVAILABLE")),
        "portfolio_allocation": options.get("portfolio_allocation", "UNAVAILABLE"),
        "greeks": options.get("greeks", "UNAVAILABLE"),
        "assignment_risk": options.get("assignment_risk", "UNAVAILABLE"),
        "volatility_risk": options.get("volatility_risk", "UNAVAILABLE"),
        "stress_tests": options.get("stress_tests", "UNAVAILABLE"),
        "alerts": options.get("alerts", []),
        "certification": options.get("certification", "UNAVAILABLE"),
        "operational_readiness": options.get("operational_readiness", "UNAVAILABLE"),
        "data_source": options.get("data_source", "UNAVAILABLE"),
        "source": options.get("source", options.get("data_source", "UNAVAILABLE")),
        "provenance": options.get("provenance", {}),
        "state_hash": options.get("state_hash", "UNAVAILABLE"),
        "generated_at": options.get("generated_at", "UNAVAILABLE"),
        "last_successful_refresh": options.get("last_successful_refresh", "UNAVAILABLE"),
        "missing_dependencies": options.get("missing_dependencies", []),
        "opportunity_count": options.get("opportunity_count", len(options.get("opportunities", []) or [])),
        "advisory_only": True,
        "execution_blocked": True,
        "execution_authority": options.get("execution_authority", "BLOCKED"),
    }


def _brokers(broker: Mapping[str, Any], runtime_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    from backend.app.brokers.canonical_tier1 import get_canonical_broker_registry

    canonical = broker.get("canonical_broker_runtime_state") if isinstance(broker.get("canonical_broker_runtime_state"), Mapping) else {}
    runtime_broker = runtime_snapshot.get("broker") if isinstance(runtime_snapshot.get("broker"), Mapping) else {}
    if _runtime_unavailable(runtime_snapshot):
        runtime_broker = {
            "selected_broker": "UNAVAILABLE",
            "broker_mode": "UNAVAILABLE",
            "transport": "UNAVAILABLE",
            "authentication": "UNAVAILABLE",
            "account": "UNAVAILABLE",
            "market_data": "UNAVAILABLE",
            "balances": "UNAVAILABLE",
            "buying_power": "UNAVAILABLE",
            "margin": "UNAVAILABLE",
            "execution_scope": "READ_ONLY",
        }
    active = {
        "selected_broker": runtime_broker.get("selected_broker", broker.get("selected_broker", "UNAVAILABLE")),
        "broker_mode": runtime_broker.get("broker_mode", broker.get("broker_mode", "UNAVAILABLE")),
        "provider_version": broker.get("provider_version", DATA_UNAVAILABLE),
        "connection_status": runtime_broker.get("transport", broker.get("connection_status", DATA_UNAVAILABLE)),
        "authentication_status": runtime_broker.get("authentication", broker.get("authentication_status", DATA_UNAVAILABLE)),
        "account_status": runtime_broker.get("account", canonical.get("account_status", broker.get("account_data_health", DATA_UNAVAILABLE))),
        "market_data_status": runtime_broker.get("market_data", broker.get("market_data_status", DATA_UNAVAILABLE)),
        "balance_status": runtime_broker.get("balances", canonical.get("balance_status", broker.get("balance_position_status", DATA_UNAVAILABLE))),
        "buying_power_status": runtime_broker.get("buying_power", canonical.get("buying_power_status", DATA_UNAVAILABLE)),
        "margin_status": runtime_broker.get("margin", canonical.get("margin_status", DATA_UNAVAILABLE)),
        "latency": broker.get("latency_ms", DATA_UNAVAILABLE),
        "freshness": broker.get("last_successful_sync", DATA_UNAVAILABLE),
        "capabilities": broker.get("supported_assets", []),
        "supported_asset_classes": broker.get("supported_assets", []),
        "supported_order_types": ["DISPLAY_ONLY"],
        "execution_scope": runtime_broker.get("execution_scope", broker.get("execution_scope", "READ_ONLY")),
        "canonical_state_hash": runtime_broker.get("state_hash", canonical.get("state_hash", broker.get("state_hash", DATA_UNAVAILABLE))),
        "state_provenance": runtime_broker.get("provenance", canonical.get("status_provenance", broker.get("status_provenance", {}))),
        "failure_reason": runtime_broker.get("failure_reason", canonical.get("failure_reason", broker.get("failure_reason", DATA_UNAVAILABLE))),
        "warnings": runtime_broker.get("warnings", broker.get("warning_reasons", [])),
    }
    registry = get_canonical_broker_registry()
    return {
        "active_broker": active,
        "broker_list": build_broker_registry(broker),
        "primary_roles": registry.primary_roles(),
        "tier1_brokers": list(registry.list_brokers()),
        "selection": {
            "enabled": False,
            "mode": "PREVIEW_ONLY_MC001",
            "arming_available": False,
            "can_change_credentials": False,
            "can_override_safety_gates": False,
        },
        "onboarding": {
            "enabled": False,
            "mode": "SHELL_ONLY_MC001",
            "credential_storage": "NOT_AVAILABLE",
            "fields": ["provider_name", "adapter_type", "environment", "capabilities", "supported_assets", "readiness_checklist"],
            "requirements": ["credential_requirements", "account_requirements", "market_data_requirements", "permission_requirements"],
        },
        "safety": {
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
            "pilot_state": broker.get("live_micro_pilot_state", "DISARMED"),
            "operator_intent": broker.get("operator_requested_live", False),
            "capital_governor": broker.get("capital_governor", DATA_UNAVAILABLE),
            "unified_trade_gate": DATA_UNAVAILABLE,
            "margin_gate": DATA_UNAVAILABLE,
            "anti_bleed_guard": DATA_UNAVAILABLE,
            "kill_switch": DATA_UNAVAILABLE,
        },
    }


def _alerts(dashboard_state: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = dashboard_state.get("alerts") if isinstance(dashboard_state, Mapping) else {}
    if not isinstance(raw, Mapping):
        raw = {}
    return {
        "active_alerts": raw.get("active", []),
        "count": raw.get("count", 0),
        "severity": raw.get("severity", "UNAVAILABLE"),
        "incident_timeline": raw.get("incident_timeline", []),
        "external_notifications": "DISABLED_MC001",
    }


def _alerts_from_runtime(alerts: Mapping[str, Any], runtime_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    runtime_alerts = runtime_snapshot.get("alerts") if isinstance(runtime_snapshot.get("alerts"), Mapping) else {}
    return {
        **alerts,
        "active_alerts": runtime_alerts.get("active_alerts", alerts.get("active_alerts", [])),
        "count": runtime_alerts.get("count", alerts.get("count", "UNAVAILABLE")),
        "heartbeat_status": runtime_alerts.get("heartbeat_status", runtime_snapshot.get("heartbeat_status", "UNAVAILABLE")),
    }


def _certification(certification: Mapping[str, Any], broker: Mapping[str, Any], runtime_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    runtime_certification = runtime_snapshot.get("certification") if isinstance(runtime_snapshot.get("certification"), Mapping) else {}
    oi_cert = runtime_certification.get("options_income_certification", DATA_UNAVAILABLE)
    try:
        from backend.options.options_income_runtime_service import build_mission_control_options_income

        oi = build_mission_control_options_income()
        cert_block = oi.get("certification") if isinstance(oi.get("certification"), Mapping) else {}
        if cert_block.get("outcome"):
            oi_cert = cert_block.get("outcome")
    except Exception:
        pass
    return {
        "rc1_platform_certification": runtime_certification.get("rc1_certification", certification.get("certification", DATA_UNAVAILABLE)),
        "rc1_operational_readiness": runtime_certification.get("rc1_operational_readiness", certification.get("operational_state", DATA_UNAVAILABLE)),
        "options_income_certification": oi_cert,
        "broker_readiness": runtime_certification.get("broker_readiness", broker.get("broker_health", DATA_UNAVAILABLE)),
        "runtime_readiness": runtime_certification.get("runtime_readiness", certification.get("operational_state", DATA_UNAVAILABLE)),
        "production_readiness_contribution": DATA_UNAVAILABLE,
        "live_disable_proof": {
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
        },
        "ready_for_controlled_rc1_runtime": certification.get("certification", DATA_UNAVAILABLE),
        "ready_for_live_trading": "NOT_CERTIFIED",
        "blockers": runtime_certification.get("blockers", certification.get("blocker_reasons", [])),
        "warnings": runtime_certification.get("warnings", certification.get("warning_reasons", [])),
    }


def _audit(sections: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "decision_explanations": [],
        "rules_evaluated": [],
        "supporting_metrics": {},
        "source_modules": ["dashboard.runtime.frontend_contract", "dashboard.mission_control"],
        "correlation_ids": [],
        "event_ids": [],
        "audit_evidence": sections.get("audit", {}),
        "warnings": [],
        "failures": [],
        "unavailable_data": ["live_control_actions"],
        "certification_evidence": sections.get("runtime_certification_snapshot", {}),
        "operator_actions": "READ_ONLY",
    }


def _explainability(sections: Mapping[str, Any]) -> dict[str, Any]:
    audit = sections.get("audit") if isinstance(sections.get("audit"), Mapping) else {}
    committee = sections.get("institutional_investment_committee") if isinstance(sections.get("institutional_investment_committee"), Mapping) else {}
    return {
        "decision_explanations": audit.get("decision_explanations", committee.get("committee_explanations", [])),
        "rules": audit.get("rules_evaluated", []),
        "metrics": audit.get("supporting_metrics", {}),
        "sources": ["dashboard.runtime.frontend_contract", "existing_css_explainability_surfaces"],
        "warnings": audit.get("warnings", []),
        "failures": audit.get("failures", []),
        "read_only": True,
    }


def _learning(sections: Mapping[str, Any]) -> dict[str, Any]:
    analytics = sections.get("analytics") if isinstance(sections.get("analytics"), Mapping) else {}
    return {
        "strategy_rankings": analytics.get("strategy_rankings", []),
        "asset_class_rankings": analytics.get("asset_class_rankings", []),
        "symbol_rankings": analytics.get("symbol_rankings", []),
        "outcome_attribution": analytics.get("outcome_attribution", "UNAVAILABLE"),
        "premium_capture": "UNAVAILABLE",
        "capital_efficiency": "UNAVAILABLE",
        "win_rate": analytics.get("win_rate", "UNAVAILABLE"),
        "expectancy": analytics.get("expectancy", "UNAVAILABLE"),
        "profit_factor": analytics.get("profit_factor", "UNAVAILABLE"),
        "drawdown": analytics.get("drawdown", "UNAVAILABLE"),
        "rolling_reliability": analytics.get("rolling_reliability", "UNAVAILABLE"),
        "learning_observations": analytics.get("learning_observations", []),
        "recommendations": analytics.get("recommendations", []),
        "historical_results_label": "Paper/demo unless explicitly marked otherwise",
    }


def _institutional_sources(sections: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "analytics": _section_mapping(sections, "analytics"),
        "strategy_analytics": _section_mapping(sections, "strategy_analytics"),
        "opportunity_intelligence": _section_mapping(sections, "opportunity_intelligence"),
        "capital_allocation": _section_mapping(sections, "capital_allocation_intelligence"),
        "investment_committee": _section_mapping(sections, "institutional_investment_committee"),
        "performance_attribution": _section_mapping(sections, "performance_attribution"),
        "execution_analytics": _section_mapping(sections, "execution_analytics"),
    }


def _governance(frontend: Mapping[str, Any], governance: Mapping[str, Any]) -> dict[str, Any]:
    session = frontend.get("session") if isinstance(frontend.get("session"), Mapping) else {}
    return {
        "current_user": session.get("user_id", DATA_UNAVAILABLE),
        "role": session.get("role", DATA_UNAVAILABLE),
        "unit": session.get("unit", DATA_UNAVAILABLE),
        "session": session.get("session_id", frontend.get("session_id", DATA_UNAVAILABLE)),
        "permissions": {
            "can_arm_broker": False,
            "can_live_mode": False,
            "can_paper_execute": False,
        },
        "session_age": DATA_UNAVAILABLE,
        "authentication_source": "EXISTING_CSS_SESSION",
        "allowed_engine_modes": ["SAFE", "CONSERVATIVE", "BALANCED", "AGGRESSIVE", "EXPANSION"],
        "governance_status": governance.get("governance_status", DATA_UNAVAILABLE),
        "rbac_summary": "READ_ONLY_MC001",
        "approval_workflows": governance.get("approval_workflows", {}),
    }


def _configuration(frontend: Mapping[str, Any], broker: Mapping[str, Any], sections: Mapping[str, Any]) -> dict[str, Any]:
    configuration = _section_mapping(sections, "configuration")
    return {
        "runtime_mode": frontend.get("resolved_mode", DATA_UNAVAILABLE),
        "engine_mode": (frontend.get("session") or {}).get("engine_mode", DATA_UNAVAILABLE) if isinstance(frontend.get("session"), Mapping) else DATA_UNAVAILABLE,
        "cycle_mode": DATA_UNAVAILABLE,
        "selected_broker": broker.get("selected_broker", "NONE"),
        "canonical_order_limit_configuration": "READ_ONLY_SUMMARY",
        "paper_limits": "CONFIGURED_IN_EXISTING_POLICY",
        "preview_limits": "CONFIGURED_IN_EXISTING_POLICY",
        "live_pilot_limits": "CONFIGURED_IN_EXISTING_POLICY",
        "feature_flags": configuration.get("feature_flags", frontend.get("feature_flags", {})),
        "service_endpoints": "REDACTED_SAFE_SUMMARY",
        "data_refresh_settings": DATA_UNAVAILABLE,
        "live_limit_overrides": "DISABLED_MC001",
    }


def _documentation_index() -> dict[str, Any]:
    return {
        "architecture": ["docs/architecture/CSS_MISSION_CONTROL_ARCHITECTURE.md"],
        "governance": [
            "docs/governance/PHASE_MC_001_MISSION_CONTROL_FOUNDATION.md",
            "docs/governance/PHASE_MC_002_MISSION_CONTROL_LIVE_DATA_INTEGRATION.md",
            "docs/governance/PHASE_MC_003_MISSION_CONTROL_RUNTIME_SNAPSHOT_INTEGRATION.md",
            "docs/governance/PHASE_MC_004_ACTIVE_RUNTIME_PUBLISHER_BINDING.md",
            "docs/governance/PHASE_MC_005_OPERATIONS_COMMAND_CENTER.md",
            "docs/governance/PHASE_MC_006_DECISION_INTELLIGENCE.md",
            "docs/governance/PHASE_MC_007A_INSTITUTIONAL_INTELLIGENCE.md",
            "docs/governance/PHASE_MC_007B_SECURE_OPERATIONS.md",
            "docs/governance/MISSION_CONTROL_FINAL_CERTIFICATION.md",
        ],
        "release_reports": [],
        "certification_reports": [],
        "operator_runbooks": [],
        "mission_control_runbooks": [
            "docs/runbooks/MISSION_CONTROL_OPERATOR_GUIDE.md",
            "docs/runbooks/MISSION_CONTROL_ADMIN_GUIDE.md",
            "docs/runbooks/MISSION_CONTROL_DISASTER_RECOVERY.md",
            "docs/runbooks/MISSION_CONTROL_DEPLOYMENT_GUIDE.md",
            "docs/runbooks/MISSION_CONTROL_RUNTIME_VALIDATION.md",
        ],
        "rollback_instructions": [],
        "broker_onboarding_guides": [],
        "incident_procedures": [],
        "rc1_validation_reports": [],
        "options_income_documentation": [],
        "browser_paths_expose_absolute_paths": False,
    }


def _data_freshness(
    frontend: Mapping[str, Any],
    broker: Mapping[str, Any],
    certification: Mapping[str, Any],
    freshness: Mapping[str, Any],
    runtime_snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    # Phase 172A: "last_runtime_heartbeat" must be the CANONICAL supervisor
    # heartbeat (runtime/supervisor/css_runtime_supervisor_state.json,
    # published by launcher/css_runtime_launcher.py), not broker connectivity
    # data. runtime_snapshot["last_heartbeat"] is populated by
    # RuntimeSnapshotProvider -> RuntimeSourceResolver -> RuntimeArtifactReader
    # from that canonical artifact (see backend/runtime/canonical_runtime_snapshot.py).
    snapshot = runtime_snapshot if isinstance(runtime_snapshot, Mapping) else {}
    canonical_heartbeat = snapshot.get("last_heartbeat", DATA_UNAVAILABLE)
    return {
        "generated_at": frontend.get("generated_at", DATA_UNAVAILABLE),
        "last_runtime_heartbeat": canonical_heartbeat if canonical_heartbeat not in (None, "", DATA_UNAVAILABLE) else broker.get("last_heartbeat", broker.get("last_successful_sync", DATA_UNAVAILABLE)),
        "broker_freshness": broker.get("last_successful_sync", DATA_UNAVAILABLE),
        "certification_freshness": certification.get("generated_at", DATA_UNAVAILABLE),
        "overall_freshness": freshness.get("overall_freshness", DATA_UNAVAILABLE),
        "stale_mandatory_data": bool(freshness.get("stale_mandatory_data")),
        "sections": freshness.get("sections", {}),
    }


def _first_status(*values: Any) -> str:
    for value in values:
        if value not in (None, "", DATA_UNAVAILABLE, "UNKNOWN"):
            return str(value)
    return DATA_UNAVAILABLE


def _runtime_unavailable(runtime_snapshot: Mapping[str, Any]) -> bool:
    return str(runtime_snapshot.get("source", "")).upper() in {"", "UNAVAILABLE", "UNKNOWN"} or str(runtime_snapshot.get("runtime_status", "")).upper() in {"OFFLINE", "UNAVAILABLE"}


def _section_mapping(sections: Mapping[str, Any], key: str) -> dict[str, Any]:
    value = sections.get(key)
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_lease_health(source: Mapping[str, Any]) -> list[Any]:
    for key in ("lease_health", "secret_lease_health"):
        value = source.get(key)
        if isinstance(value, list):
            return value
    return []


def _safe_enterprise_broker_runtime_source(source: Mapping[str, Any]) -> dict[str, Any]:
    safe = {
        str(key): value
        for key, value in dict(source or {}).items()
        if str(key) != "secret_lease_health"
    }
    if "lease_health" not in safe:
        safe["lease_health"] = _safe_lease_health(source)
    return safe


def _panel_preserves_read_only_safety(panel: Mapping[str, Any]) -> bool:
    return (
        panel.get("read_only") is True
        and panel.get("execution_allowed") is False
        and panel.get("live_trading_blocked") is True
        and panel.get("broker_execution_armed") is False
        and panel.get("advisory_only") is True
    )


def _profit_protection_governance_source(
    dashboard_state: Mapping[str, Any] | None,
    frontend: Mapping[str, Any],
    runtime_snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    sections = frontend.get("sections") if isinstance(frontend.get("sections"), Mapping) else {}
    candidates = (
        dashboard_state.get("profit_protection_governance")
        if isinstance(dashboard_state, Mapping)
        else None,
        sections.get("profit_protection_governance"),
        (sections.get("execution") or {}).get("profit_protection_governance")
        if isinstance(sections.get("execution"), Mapping)
        else None,
        runtime_snapshot.get("profit_protection_governance"),
    )
    for candidate in candidates:
        if isinstance(candidate, Mapping):
            return dict(candidate)
    return {}


def _scan_non_finite(value: Any, *, reasons: list[str], path: str = "") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            _scan_non_finite(item, reasons=reasons, path=f"{path}.{key}" if path else str(key))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _scan_non_finite(item, reasons=reasons, path=f"{path}[{index}]")
    elif isinstance(value, float) and not isfinite(value):
        reasons.append(f"non_finite_value:{path}")


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


__all__ = [
    "MISSION_CONTROL_SCHEMA_VERSION",
    "build_mission_control_state",
    "mission_control_state_json",
    "validate_mission_control_state",
]
