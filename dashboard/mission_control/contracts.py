from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from math import isfinite
from typing import Any

from dashboard.mission_control.broker_telemetry import build_broker_telemetry
from dashboard.mission_control.committee_projection import build_committee_view
from dashboard.mission_control.counterfactual_projection import build_counterfactual_projection
from dashboard.mission_control.decision_intelligence import build_decision_panel
from dashboard.mission_control.decision_trace import build_decision_trace
from dashboard.mission_control.evidence_graph import build_evidence_graph
from dashboard.mission_control.event_stream import build_alert_center, build_event_stream
from dashboard.mission_control.explanation_projection import build_decision_explanation
from dashboard.mission_control.freshness import build_freshness_summary
from dashboard.mission_control.health import build_health_summary
from dashboard.mission_control.navigation import navigation_payload
from dashboard.mission_control.operations_timeline import build_operations_timeline
from dashboard.mission_control.permissions import mission_control_permissions_payload, validate_read_only_permissions
from dashboard.mission_control.portfolio_projection import build_options_income_panel, build_performance_panel, build_portfolio_command_view
from dashboard.mission_control.recommendation_projection import build_recommendation_panel
from dashboard.mission_control.risk_projection import build_risk_command_view
from dashboard.mission_control.runtime_snapshot_normalizer import normalize_runtime_snapshot
from dashboard.mission_control.safety import SAFE_FLAGS, mission_control_safety_payload, normalize_metric, validate_no_secret_payload
from dashboard.mission_control.serializers import state_hash, validate_serializable_payload
from dashboard.mission_control.source_registry import build_source_registry
from dashboard.mission_control.state_adapter import build_broker_registry, frontend_payload_from_runtime, section
from dashboard.mission_control.system_metrics import build_executive_kpi_board, build_source_consistency, build_system_metrics
from dashboard.mission_control.trade_lifecycle import build_trade_lifecycle
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
        "runtime_snapshot": runtime_snapshot,
        "platform": _platform(frontend, broker, certification, safety, runtime_snapshot),
        "runtime": _runtime(frontend, governance, certification, runtime_snapshot),
        "trading": _trading(execution, positions),
        "portfolio": _portfolio(account, positions, pnl, runtime_snapshot),
        "market_intelligence": _market(market, runtime_snapshot),
        "risk": _risk(risk, governance, runtime_snapshot),
        "options_income": _options_income(sections),
        "brokers": _brokers(broker, runtime_snapshot),
        "alerts": _alerts_from_runtime(alerts, runtime_snapshot),
        "certification": _certification(certification, broker, runtime_snapshot),
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
    state["source_consistency"] = build_source_consistency(state)
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
    return normalize_runtime_snapshot(dashboard_state, frontend)


def _platform(frontend: Mapping[str, Any], broker: Mapping[str, Any], certification: Mapping[str, Any], safety: Mapping[str, Any], runtime_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    runtime_broker = runtime_snapshot.get("broker") if isinstance(runtime_snapshot.get("broker"), Mapping) else {}
    selected_broker = "UNAVAILABLE" if _runtime_unavailable(runtime_snapshot) else runtime_broker.get("selected_broker", broker.get("selected_broker", "UNAVAILABLE"))
    broker_health = "UNAVAILABLE" if _runtime_unavailable(runtime_snapshot) else runtime_broker.get("broker_health", broker.get("broker_health", "UNAVAILABLE"))
    return {
        "product": "CSS Mission Control",
        "platform_status": _first_status(runtime_snapshot.get("runtime_health"), certification.get("certification"), runtime_broker.get("broker_health"), "UNAVAILABLE"),
        "runtime_health": runtime_snapshot.get("runtime_health", "UNAVAILABLE"),
        "runtime_mode": runtime_snapshot.get("runtime_mode", frontend.get("resolved_mode", "UNAVAILABLE")),
        "engine_mode": runtime_snapshot.get("engine_mode", "UNAVAILABLE"),
        "cycle": runtime_snapshot.get("cycle", "UNAVAILABLE"),
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
    return {
        "runtime_id": runtime_snapshot.get("runtime_id", DATA_UNAVAILABLE),
        "runtime_status": runtime_snapshot.get("runtime_status", certification.get("operational_state", DATA_UNAVAILABLE)),
        "runtime_mode": runtime_snapshot.get("runtime_mode", frontend.get("resolved_mode", DATA_UNAVAILABLE)),
        "engine_mode": runtime_snapshot.get("engine_mode", session.get("engine_mode", DATA_UNAVAILABLE)),
        "cycle_mode": runtime_snapshot.get("cycle_mode", DATA_UNAVAILABLE),
        "cycle": runtime_snapshot.get("cycle", session.get("cycle_number", 0)),
        "uptime": runtime_snapshot.get("uptime_seconds", DATA_UNAVAILABLE),
        "heartbeat": runtime_snapshot.get("last_heartbeat", frontend.get("generated_at", DATA_UNAVAILABLE)),
        "heartbeat_status": runtime_snapshot.get("heartbeat_status", DATA_UNAVAILABLE),
        "heartbeat_age_seconds": runtime_snapshot.get("heartbeat_age_seconds", DATA_UNAVAILABLE),
        "last_successful_cycle": runtime_snapshot.get("last_successful_cycle", DATA_UNAVAILABLE),
        "last_failed_cycle": runtime_snapshot.get("last_failed_cycle", DATA_UNAVAILABLE),
        "supervisor_state": runtime_snapshot.get("runtime_status", DATA_UNAVAILABLE),
        "restart_count": runtime_snapshot.get("restart_count", DATA_UNAVAILABLE),
        "failure_count": runtime_snapshot.get("failure_count", DATA_UNAVAILABLE),
        "recovery_count": runtime_snapshot.get("recovery_count", DATA_UNAVAILABLE),
        "alert_count": runtime_snapshot.get("alert_count", DATA_UNAVAILABLE),
        "disconnect_count": runtime_snapshot.get("disconnect_count", DATA_UNAVAILABLE),
        "state_hash": runtime_snapshot.get("state_hash", DATA_UNAVAILABLE),
        "source": runtime_snapshot.get("source", DATA_UNAVAILABLE),
        "source_diagnostics": runtime_snapshot.get("source_diagnostics", {}),
        "subsystem_health": {
            "audit": governance.get("audit_enabled", DATA_UNAVAILABLE),
            "api": "AVAILABLE" if runtime_snapshot.get("source") in active_runtime_sources else DATA_UNAVAILABLE,
            "dashboard": "AVAILABLE",
            "mobile": "AVAILABLE" if runtime_snapshot.get("source") in active_runtime_sources else DATA_UNAVAILABLE,
            "certification": certification.get("certification", DATA_UNAVAILABLE),
        },
        "controls": {"restart": "DISABLED_MC001", "shutdown": "DISABLED_MC001"},
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


def _portfolio(account: Mapping[str, Any], positions: Mapping[str, Any], pnl: Mapping[str, Any], runtime_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    runtime_portfolio = runtime_snapshot.get("portfolio") if isinstance(runtime_snapshot.get("portfolio"), Mapping) else {}
    if _runtime_unavailable(runtime_snapshot):
        return {
            "equity": "UNAVAILABLE",
            "cash": "UNAVAILABLE",
            "buying_power": "UNAVAILABLE",
            "total_exposure": "UNAVAILABLE",
            "capital_deployed": "UNAVAILABLE",
            "capital_available": "UNAVAILABLE",
            "realized_pnl": "UNAVAILABLE",
            "unrealized_pnl": "UNAVAILABLE",
            "net_pnl": "UNAVAILABLE",
            "open_positions": "UNAVAILABLE",
            "positions": [],
            "asset_allocation": {},
            "sector_allocation": "UNAVAILABLE",
            "currency_exposure": "UNAVAILABLE",
            "pnl_by_asset_class": {},
            "pnl_by_strategy": "UNAVAILABLE",
            "collateral_utilization": "UNAVAILABLE",
            "capital_efficiency": "UNAVAILABLE",
            "drawdown": "UNAVAILABLE",
            "performance_attribution": "UNAVAILABLE",
        }
    return {
        "equity": normalize_metric(runtime_portfolio.get("equity", account.get("total_equity"))),
        "cash": normalize_metric(runtime_portfolio.get("cash", account.get("cash_balance"))),
        "buying_power": normalize_metric(runtime_portfolio.get("buying_power", account.get("buying_power"))),
        "total_exposure": normalize_metric(runtime_portfolio.get("exposure", positions.get("total_exposure", DATA_UNAVAILABLE))),
        "capital_deployed": normalize_metric(runtime_portfolio.get("capital_deployed", positions.get("total_exposure", DATA_UNAVAILABLE))),
        "capital_available": normalize_metric(runtime_portfolio.get("capital_available", account.get("buying_power"))),
        "realized_pnl": normalize_metric(runtime_portfolio.get("realized_pnl", pnl.get("realized_pnl", DATA_UNAVAILABLE))),
        "unrealized_pnl": normalize_metric(runtime_portfolio.get("unrealized_pnl", pnl.get("unrealized_pnl", DATA_UNAVAILABLE))),
        "net_pnl": normalize_metric(runtime_portfolio.get("net_pnl", pnl.get("net_pnl", DATA_UNAVAILABLE))),
        "open_positions": runtime_portfolio.get("open_positions", positions.get("total", DATA_UNAVAILABLE)),
        "positions": runtime_portfolio.get("positions", positions.get("open_positions", [])),
        "asset_allocation": runtime_portfolio.get("asset_allocation", positions.get("asset_counts", {})),
        "sector_allocation": DATA_UNAVAILABLE,
        "currency_exposure": account.get("currency", "USD"),
        "pnl_by_asset_class": runtime_portfolio.get("pnl_by_asset", pnl.get("asset_unrealized_pnl", {})),
        "pnl_by_strategy": runtime_portfolio.get("pnl_by_strategy", DATA_UNAVAILABLE),
        "collateral_utilization": normalize_metric(account.get("margin_used")),
        "capital_efficiency": DATA_UNAVAILABLE,
        "drawdown": normalize_metric(runtime_portfolio.get("drawdown", DATA_UNAVAILABLE)),
        "performance_attribution": DATA_UNAVAILABLE,
    }


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


def _brokers(broker: Mapping[str, Any], runtime_snapshot: Mapping[str, Any]) -> dict[str, Any]:
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
    return {
        "rc1_platform_certification": runtime_certification.get("rc1_certification", certification.get("certification", DATA_UNAVAILABLE)),
        "rc1_operational_readiness": runtime_certification.get("rc1_operational_readiness", certification.get("operational_state", DATA_UNAVAILABLE)),
        "options_income_certification": runtime_certification.get("options_income_certification", DATA_UNAVAILABLE),
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
            "docs/governance/PHASE_MC_003_MISSION_CONTROL_RUNTIME_SNAPSHOT_INTEGRATION.md",
            "docs/governance/PHASE_MC_004_ACTIVE_RUNTIME_PUBLISHER_BINDING.md",
            "docs/governance/PHASE_MC_005_OPERATIONS_COMMAND_CENTER.md",
            "docs/governance/PHASE_MC_006_DECISION_INTELLIGENCE.md",
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


def _runtime_unavailable(runtime_snapshot: Mapping[str, Any]) -> bool:
    return str(runtime_snapshot.get("source", "")).upper() in {"", "UNAVAILABLE", "UNKNOWN"} or str(runtime_snapshot.get("runtime_status", "")).upper() in {"OFFLINE", "UNAVAILABLE"}


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
