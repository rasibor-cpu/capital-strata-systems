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
    source_diagnostics = _mapping(runtime.get("source_diagnostics"))
    return {
        "cpu": DATA_UNAVAILABLE,
        "memory": DATA_UNAVAILABLE,
        "runtime_latency": DATA_UNAVAILABLE,
        "api_latency": DATA_UNAVAILABLE,
        "refresh_interval_seconds": 5,
        "event_queue": DATA_UNAVAILABLE,
        "cycle_duration": DATA_UNAVAILABLE,
        "runtime_age": runtime.get("uptime", DATA_UNAVAILABLE),
        "heartbeat_age": runtime.get("heartbeat_age_seconds", DATA_UNAVAILABLE),
        "source_selected": source_diagnostics.get("selected_source", runtime.get("source", DATA_UNAVAILABLE)),
        "source_candidate_count": source_diagnostics.get("candidate_count", DATA_UNAVAILABLE),
        "metrics_controls": "DISABLED_READ_ONLY",
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
