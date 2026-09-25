from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dashboard.runtime.frontend_contract import DATA_UNAVAILABLE


def build_executive_kpi_board(state: Mapping[str, Any]) -> dict[str, Any]:
    runtime = _mapping(state.get("runtime"))
    platform = _mapping(state.get("platform"))
    brokers = _mapping(state.get("brokers"))
    portfolio = _mapping(state.get("portfolio"))
    risk = _mapping(state.get("risk"))
    market = _mapping(state.get("market_intelligence"))
    alerts = _mapping(state.get("alerts"))
    trading = _mapping(state.get("trading"))
    certification = _mapping(state.get("certification"))
    active_broker = _mapping(brokers.get("active_broker"))
    return {
        "uptime": runtime.get("uptime", DATA_UNAVAILABLE),
        "runtime_health": platform.get("runtime_health", DATA_UNAVAILABLE),
        "broker_health": active_broker.get("connection_status", platform.get("broker_health", DATA_UNAVAILABLE)),
        "portfolio_health": "AVAILABLE" if portfolio.get("equity") != DATA_UNAVAILABLE else DATA_UNAVAILABLE,
        "risk_health": risk.get("overall_risk_state", DATA_UNAVAILABLE),
        "market_health": market.get("market_regime", DATA_UNAVAILABLE),
        "alert_count": alerts.get("count", DATA_UNAVAILABLE),
        "trade_quality": trading.get("execution_quality", DATA_UNAVAILABLE),
        "execution_quality": trading.get("execution_quality", DATA_UNAVAILABLE),
        "system_readiness": platform.get("platform_status", DATA_UNAVAILABLE),
        "rc1_readiness": certification.get("rc1_operational_readiness", DATA_UNAVAILABLE),
        "read_only": True,
        **_metadata(state, "executive_kpi_board"),
    }


def build_system_metrics(state: Mapping[str, Any]) -> dict[str, Any]:
    runtime = _mapping(state.get("runtime"))
    snapshot = _mapping(state.get("runtime_snapshot"))
    brokers = _mapping(state.get("brokers"))
    active_broker = _mapping(brokers.get("active_broker"))
    source_diagnostics = _mapping(runtime.get("source_diagnostics"))
    runtime_metrics = _mapping(runtime.get("metrics"))
    snapshot_metrics = _mapping(snapshot.get("metrics"))

    def first(*values: Any) -> Any:
        for value in values:
            if value not in (None, "", DATA_UNAVAILABLE, "UNAVAILABLE"):
                return value
        return DATA_UNAVAILABLE

    return {
        "cpu": first(
            runtime_metrics.get("cpu"),
            runtime_metrics.get("cpu_percent"),
            snapshot_metrics.get("cpu"),
            snapshot.get("cpu"),
            snapshot.get("cpu_percent"),
        ),
        "memory": first(
            runtime_metrics.get("memory"),
            runtime_metrics.get("memory_percent"),
            snapshot_metrics.get("memory"),
            snapshot.get("memory"),
            snapshot.get("memory_percent"),
        ),
        "runtime_latency": first(
            runtime_metrics.get("runtime_latency"),
            runtime_metrics.get("latency_ms"),
            snapshot_metrics.get("runtime_latency"),
            snapshot.get("runtime_latency"),
        ),
        "api_latency": first(
            runtime_metrics.get("api_latency"),
            snapshot_metrics.get("api_latency"),
            snapshot.get("api_latency"),
        ),
        "refresh_interval_seconds": first(
            runtime_metrics.get("refresh_interval_seconds"),
            snapshot_metrics.get("refresh_interval_seconds"),
            5,
        ),
        "event_queue": first(
            runtime_metrics.get("event_queue"),
            runtime_metrics.get("queue_depth"),
            snapshot_metrics.get("event_queue"),
            snapshot.get("event_queue"),
        ),
        "cycle_duration": first(
            runtime_metrics.get("cycle_duration"),
            runtime_metrics.get("cycle_duration_seconds"),
            snapshot_metrics.get("cycle_duration"),
            snapshot.get("cycle_duration"),
        ),
        "runtime_age": first(runtime.get("uptime"), snapshot.get("uptime")),
        "heartbeat_age": first(runtime.get("heartbeat_age_seconds"), snapshot.get("heartbeat_age_seconds")),
        "source_selected": source_diagnostics.get("selected_source", runtime.get("source", snapshot.get("source", DATA_UNAVAILABLE))),
        "source_candidate_count": source_diagnostics.get("candidate_count", DATA_UNAVAILABLE),
        "active_broker": active_broker.get("selected_broker", DATA_UNAVAILABLE),
        "broker_mode": active_broker.get("broker_mode", DATA_UNAVAILABLE),
        "metrics_controls": "AUTO_SOURCE_READ_ONLY",
        "read_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
        **_metadata(state, "system_metrics"),
    }


def build_source_consistency(state: Mapping[str, Any]) -> dict[str, Any]:
    runtime = _mapping(state.get("runtime"))
    runtime_hash = runtime.get("state_hash", DATA_UNAVAILABLE)
    sections = {
        name: _mapping(state.get(name))
        for name in (
            "operations_timeline",
            "trade_lifecycle",
            "portfolio_command",
            "broker_telemetry",
            "risk_command_center",
            "alert_center",
            "executive_kpis",
            "performance_panel",
            "options_income_panel",
            "system_metrics",
            "decision_panel",
            "decision_trace",
            "decision_explanation",
            "committee_view",
            "counterfactuals",
            "recommendation_panel",
            "evidence_graph",
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
        )
    }
    mismatches = [
        name
        for name, payload in sections.items()
        if payload and payload.get("state_hash", runtime_hash) not in {runtime_hash, DATA_UNAVAILABLE}
    ]
    return {
        "status": "FAIL_CLOSED" if mismatches else "PASS",
        "runtime_state_hash": runtime_hash,
        "checked_sections": sorted(name for name, payload in sections.items() if payload),
        "mismatches": sorted(mismatches),
        "demo_runtime_mixing": bool(state.get("mock_data")) and runtime.get("source") not in {"MOCK", "DEMO", "UNAVAILABLE"},
        "read_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
        **_metadata(state, "source_consistency"),
    }


def _metadata(state: Mapping[str, Any], source_module: str) -> dict[str, Any]:
    runtime = _mapping(state.get("runtime"))
    snapshot = _mapping(state.get("runtime_snapshot"))
    freshness = _mapping(state.get("freshness"))
    return {
        "source": runtime.get("source", snapshot.get("source", DATA_UNAVAILABLE)),
        "source_module": f"dashboard.mission_control.{source_module}",
        "provenance": snapshot.get("provenance", {}),
        "generated_at": state.get("generated_at", DATA_UNAVAILABLE),
        "freshness": freshness.get("overall_freshness", DATA_UNAVAILABLE),
        "state_hash": runtime.get("state_hash", snapshot.get("state_hash", DATA_UNAVAILABLE)),
    }


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


__all__ = ["build_executive_kpi_board", "build_source_consistency", "build_system_metrics"]
