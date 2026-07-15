from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from math import isfinite
from typing import Any

from dashboard.mission_control.freshness import build_freshness_summary
from dashboard.mission_control.health import build_health_summary
from dashboard.mission_control.navigation import navigation_payload
from dashboard.mission_control.permissions import mission_control_permissions_payload, validate_read_only_permissions
from dashboard.mission_control.safety import SAFE_FLAGS, mission_control_safety_payload, normalize_metric, validate_no_secret_payload
from dashboard.mission_control.serializers import state_hash, validate_serializable_payload
from dashboard.mission_control.source_registry import build_source_registry
from dashboard.mission_control.state_adapter import build_broker_registry, frontend_payload_from_runtime, section
from dashboard.runtime.frontend_contract import DATA_UNAVAILABLE


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
    safety = mission_control_safety_payload(
        {
            **SAFE_FLAGS,
            "broker": broker,
            "certification": certification,
            "mock_data": frontend.get("mission_control_mock_data"),
        }
    )

    state = {
        **asdict(envelope),
        "navigation": navigation_payload(),
        "platform": _platform(frontend, broker, certification, safety),
        "runtime": _runtime(frontend, governance, certification),
        "trading": _trading(execution, positions),
        "portfolio": _portfolio(account, positions, pnl),
        "market_intelligence": _market(market),
        "risk": _risk(risk, governance),
        "options_income": _options_income(sections),
        "brokers": _brokers(broker),
        "alerts": alerts,
        "certification": _certification(certification, broker),
        "audit": _audit(sections),
        "explainability": _explainability(sections),
        "learning": _learning(sections),
        "governance": _governance(frontend, governance),
        "configuration": _configuration(frontend, broker),
        "documentation": _documentation_index(),
        "permissions": mission_control_permissions_payload(),
        "safety": safety,
        "mock_data": bool(frontend.get("mission_control_mock_data")),
        "mock_data_label": "MOCK DATA - NOT LIVE" if frontend.get("mission_control_mock_data") else "RUNTIME DATA",
    }
    source_registry = build_source_registry(
        frontend,
        state,
        dashboard_state_available=bool(frontend.get("mission_control_dashboard_state_available")),
        allow_mock=allow_mock,
    )
    freshness = build_freshness_summary(source_registry)
    state["source_registry"] = source_registry
    state["data_sources"] = source_registry
    state["freshness"] = freshness
    state["data_freshness"] = _data_freshness(frontend, broker, certification, freshness)
    state["health"] = build_health_summary(state, freshness_summary=freshness)
    state["state_hash"] = state_hash({key: value for key, value in state.items() if key not in {"generated_at", "state_hash"}})
    validation = validate_mission_control_state(state)
    state["contract_validation"] = validation
    if not validation["valid"]:
        state["platform"]["platform_status"] = "FAIL_CLOSED"
        state["safety"]["fail_closed"] = True
        state["safety"]["safety_status"] = "FAIL_CLOSED"
        state["health"] = build_health_summary(state, freshness_summary=freshness)
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
    if not isinstance(source.get("navigation"), list) or len(source.get("navigation", [])) != 15:
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
    return {
        "valid": not reasons,
        "status": "PASS" if not reasons else "FAIL_CLOSED",
        "reasons": sorted(set(reasons)),
        **SAFE_FLAGS,
        "advisory_only": True,
    }


def mission_control_state_json(state: Mapping[str, Any], *, indent: int | None = None) -> str:
    return json.dumps(_json_safe(dict(state)), sort_keys=True, separators=None if indent else (",", ":"), indent=indent, default=str)


def _platform(frontend: Mapping[str, Any], broker: Mapping[str, Any], certification: Mapping[str, Any], safety: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "product": "CSS Mission Control",
        "platform_status": _first_status(certification.get("certification"), broker.get("broker_health"), "UNAVAILABLE"),
        "runtime_mode": frontend.get("resolved_mode", "UNAVAILABLE"),
        "selected_broker": broker.get("selected_broker", "NONE"),
        "broker_health": broker.get("broker_health", "UNAVAILABLE"),
        "risk_state": "UNAVAILABLE",
        "active_alerts": 0,
        "execution_authority": "BLOCKED" if not safety.get("execution_allowed") else "UNKNOWN",
        "live_trading_blocked": True,
        "last_refresh": frontend.get("generated_at", DATA_UNAVAILABLE),
    }


def _runtime(frontend: Mapping[str, Any], governance: Mapping[str, Any], certification: Mapping[str, Any]) -> dict[str, Any]:
    session = frontend.get("session") if isinstance(frontend.get("session"), Mapping) else {}
    return {
        "runtime_status": certification.get("operational_state", DATA_UNAVAILABLE),
        "runtime_mode": frontend.get("resolved_mode", DATA_UNAVAILABLE),
        "engine_mode": session.get("engine_mode", DATA_UNAVAILABLE),
        "cycle": session.get("cycle_number", 0),
        "uptime": DATA_UNAVAILABLE,
        "heartbeat": frontend.get("generated_at", DATA_UNAVAILABLE),
        "supervisor_state": DATA_UNAVAILABLE,
        "restart_count": 0,
        "failure_count": 0,
        "recovery_count": 0,
        "subsystem_health": {
            "audit": governance.get("audit_enabled", DATA_UNAVAILABLE),
            "api": DATA_UNAVAILABLE,
            "dashboard": "AVAILABLE",
            "mobile": DATA_UNAVAILABLE,
            "certification": certification.get("certification", DATA_UNAVAILABLE),
        },
        "controls": {"restart": "DISABLED_MC001", "shutdown": "DISABLED_MC001"},
    }


def _trading(execution: Mapping[str, Any], positions: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "candidate_trades": [],
        "accepted_decisions": execution.get("accepted_trades", 0),
        "rejected_decisions": execution.get("rejected_trades", 0),
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


def _portfolio(account: Mapping[str, Any], positions: Mapping[str, Any], pnl: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "equity": normalize_metric(account.get("total_equity")),
        "cash": normalize_metric(account.get("cash_balance")),
        "buying_power": normalize_metric(account.get("buying_power")),
        "total_exposure": normalize_metric(positions.get("total_exposure", DATA_UNAVAILABLE)),
        "capital_deployed": normalize_metric(positions.get("total_exposure", DATA_UNAVAILABLE)),
        "capital_available": normalize_metric(account.get("buying_power")),
        "positions": positions.get("open_positions", []),
        "asset_allocation": positions.get("asset_counts", {}),
        "sector_allocation": DATA_UNAVAILABLE,
        "currency_exposure": account.get("currency", "USD"),
        "pnl_by_asset_class": pnl.get("asset_unrealized_pnl", {}),
        "pnl_by_strategy": DATA_UNAVAILABLE,
        "collateral_utilization": normalize_metric(account.get("margin_used")),
        "capital_efficiency": DATA_UNAVAILABLE,
        "drawdown": DATA_UNAVAILABLE,
        "performance_attribution": DATA_UNAVAILABLE,
    }


def _market(market: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "market_regime": market.get("market_regime", market.get("regime_state", DATA_UNAVAILABLE)),
        "trend": market.get("trend_state", DATA_UNAVAILABLE),
        "volatility": market.get("volatility_state", DATA_UNAVAILABLE),
        "liquidity": market.get("liquidity_state", DATA_UNAVAILABLE),
        "momentum": market.get("momentum_state", DATA_UNAVAILABLE),
        "pressure": market.get("pressure_state", DATA_UNAVAILABLE),
        "probability": market.get("probability_state", DATA_UNAVAILABLE),
        "velocity": market.get("velocity_state", DATA_UNAVAILABLE),
        "vwap_state": market.get("vwap_state", DATA_UNAVAILABLE),
        "spread_quality": market.get("spread_state", DATA_UNAVAILABLE),
        "execution_cost_state": market.get("execution_cost_state", DATA_UNAVAILABLE),
        "signal_confluence": market.get("signal_confluence_state", DATA_UNAVAILABLE),
        "asset_class_rankings": [],
        "watchlists": [],
        "market_data_freshness": market.get("market_data_freshness", DATA_UNAVAILABLE),
    }


def _risk(risk: Mapping[str, Any], governance: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "overall_risk_state": risk.get("risk_state", DATA_UNAVAILABLE),
        "risk_score": risk.get("risk_score", DATA_UNAVAILABLE),
        "limit_breaches": risk.get("limit_breaches", []),
        "warnings": risk.get("warnings", []),
        "drawdown": normalize_metric(risk.get("current_drawdown")),
        "exposure": normalize_metric(risk.get("total_exposure")),
        "concentration": DATA_UNAVAILABLE,
        "liquidity_risk": DATA_UNAVAILABLE,
        "volatility_risk": DATA_UNAVAILABLE,
        "greeks": DATA_UNAVAILABLE,
        "stress_tests": DATA_UNAVAILABLE,
        "assignment_exposure": DATA_UNAVAILABLE,
        "collateral_utilization": DATA_UNAVAILABLE,
        "capital_limits": DATA_UNAVAILABLE,
        "daily_session_loss_limits": DATA_UNAVAILABLE,
        "anti_bleed_guard": governance.get("anti_bleed_guard", DATA_UNAVAILABLE),
        "unified_trade_gate": governance.get("unified_trade_gate", DATA_UNAVAILABLE),
        "margin_gate": governance.get("margin_gate", DATA_UNAVAILABLE),
        "kill_switch": governance.get("kill_switch", DATA_UNAVAILABLE),
    }


def _options_income(sections: Mapping[str, Any]) -> dict[str, Any]:
    options = sections.get("options_income") if isinstance(sections.get("options_income"), Mapping) else {}
    return {
        "status": options.get("status", "UNAVAILABLE"),
        "opportunities": options.get("opportunities", []),
        "accepted_candidates": [],
        "rejected_candidates": [],
        "covered_calls": [],
        "cash_secured_puts": [],
        "paper_positions": [],
        "premium_accounting": "UNAVAILABLE",
        "collateral": "UNAVAILABLE",
        "position_health": "UNAVAILABLE",
        "rolling_recommendations": [],
        "income_targets": "UNAVAILABLE",
        "portfolio_allocation": "UNAVAILABLE",
        "greeks": "UNAVAILABLE",
        "assignment_risk": "UNAVAILABLE",
        "volatility_risk": "UNAVAILABLE",
        "stress_tests": "UNAVAILABLE",
        "alerts": [],
        "certification": "UNAVAILABLE",
        "operational_readiness": "UNAVAILABLE",
        "data_source": options.get("data_source", "UNAVAILABLE"),
    }


def _brokers(broker: Mapping[str, Any]) -> dict[str, Any]:
    canonical = broker.get("canonical_broker_runtime_state") if isinstance(broker.get("canonical_broker_runtime_state"), Mapping) else {}
    active = {
        "selected_broker": broker.get("selected_broker", "NONE"),
        "broker_mode": broker.get("broker_mode", "paper"),
        "provider_version": broker.get("provider_version", DATA_UNAVAILABLE),
        "connection_status": broker.get("connection_status", DATA_UNAVAILABLE),
        "authentication_status": broker.get("authentication_status", DATA_UNAVAILABLE),
        "account_status": canonical.get("account_status", broker.get("account_data_health", DATA_UNAVAILABLE)),
        "market_data_status": broker.get("market_data_status", DATA_UNAVAILABLE),
        "balance_status": canonical.get("balance_status", broker.get("balance_position_status", DATA_UNAVAILABLE)),
        "buying_power_status": canonical.get("buying_power_status", DATA_UNAVAILABLE),
        "margin_status": canonical.get("margin_status", DATA_UNAVAILABLE),
        "latency": broker.get("latency_ms", DATA_UNAVAILABLE),
        "freshness": broker.get("last_successful_sync", DATA_UNAVAILABLE),
        "capabilities": broker.get("supported_assets", []),
        "supported_asset_classes": broker.get("supported_assets", []),
        "supported_order_types": ["DISPLAY_ONLY"],
        "execution_scope": broker.get("execution_scope", "READ_ONLY"),
        "canonical_state_hash": canonical.get("state_hash", broker.get("state_hash", DATA_UNAVAILABLE)),
        "state_provenance": canonical.get("status_provenance", broker.get("status_provenance", {})),
        "failure_reason": canonical.get("failure_reason", broker.get("failure_reason", DATA_UNAVAILABLE)),
        "warnings": broker.get("warning_reasons", []),
    }
    return {
        "active_broker": active,
        "broker_list": build_broker_registry(broker),
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


def _certification(certification: Mapping[str, Any], broker: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "rc1_platform_certification": certification.get("certification", DATA_UNAVAILABLE),
        "rc1_operational_readiness": certification.get("operational_state", DATA_UNAVAILABLE),
        "options_income_certification": DATA_UNAVAILABLE,
        "broker_readiness": broker.get("broker_health", DATA_UNAVAILABLE),
        "runtime_readiness": certification.get("operational_state", DATA_UNAVAILABLE),
        "production_readiness_contribution": DATA_UNAVAILABLE,
        "live_disable_proof": {
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
        },
        "ready_for_controlled_rc1_runtime": certification.get("certification", DATA_UNAVAILABLE),
        "ready_for_live_trading": "NOT_CERTIFIED",
        "blockers": certification.get("blocker_reasons", []),
        "warnings": certification.get("warning_reasons", []),
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
    }


def _configuration(frontend: Mapping[str, Any], broker: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "runtime_mode": frontend.get("resolved_mode", DATA_UNAVAILABLE),
        "engine_mode": (frontend.get("session") or {}).get("engine_mode", DATA_UNAVAILABLE) if isinstance(frontend.get("session"), Mapping) else DATA_UNAVAILABLE,
        "cycle_mode": DATA_UNAVAILABLE,
        "selected_broker": broker.get("selected_broker", "NONE"),
        "canonical_order_limit_configuration": "READ_ONLY_SUMMARY",
        "paper_limits": "CONFIGURED_IN_EXISTING_POLICY",
        "preview_limits": "CONFIGURED_IN_EXISTING_POLICY",
        "live_pilot_limits": "CONFIGURED_IN_EXISTING_POLICY",
        "feature_flags": {},
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
        ],
        "release_reports": [],
        "certification_reports": [],
        "operator_runbooks": [],
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
) -> dict[str, Any]:
    return {
        "generated_at": frontend.get("generated_at", DATA_UNAVAILABLE),
        "last_runtime_heartbeat": broker.get("last_heartbeat", broker.get("last_successful_sync", DATA_UNAVAILABLE)),
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
