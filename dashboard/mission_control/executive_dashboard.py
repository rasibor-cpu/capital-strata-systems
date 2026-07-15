from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dashboard.runtime.frontend_contract import DATA_UNAVAILABLE


def build_institutional_executive_dashboard(state: Mapping[str, Any]) -> dict[str, Any]:
    platform = _mapping(state.get("platform"))
    kpis = _mapping(state.get("executive_kpis"))
    portfolio = _mapping(state.get("portfolio_command"))
    capital = _mapping(state.get("capital_committee"))
    committees = _mapping(state.get("committee_view"))
    alerts = _mapping(state.get("alert_center"))
    opportunities = _mapping(state.get("opportunity_ranking"))
    return {
        "status": "FAIL_CLOSED" if _runtime_unavailable(state) else platform.get("platform_status", DATA_UNAVAILABLE),
        "platform_health": platform.get("platform_status", DATA_UNAVAILABLE),
        "investment_health": _mapping(state.get("investment_committee")).get("status", DATA_UNAVAILABLE),
        "risk_health": _mapping(state.get("risk_committee")).get("risk_posture", DATA_UNAVAILABLE),
        "broker_health": kpis.get("broker_health", DATA_UNAVAILABLE),
        "runtime_health": kpis.get("runtime_health", DATA_UNAVAILABLE),
        "portfolio_health": kpis.get("portfolio_health", DATA_UNAVAILABLE),
        "capital_health": capital.get("status", portfolio.get("status", DATA_UNAVAILABLE)),
        "committee_summary": committees.get("committees", []),
        "top_alerts": alerts.get("alerts", alerts.get("active_alerts", []))[:5] if isinstance(alerts.get("alerts", alerts.get("active_alerts", [])), list) else [],
        "top_opportunities": opportunities.get("opportunities", [])[:5] if isinstance(opportunities.get("opportunities"), list) else [],
        "links": _links("executive_overview", "risk_command", "portfolio", "audit_explainability"),
        "read_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
        **_metadata(state, "executive_dashboard"),
    }


def _links(*keys: str) -> list[dict[str, str]]:
    return [{"label": key.replace("_", " ").title(), "route": f"/mission-control/{key.replace('_', '-')}"} for key in keys]


def _metadata(state: Mapping[str, Any], source_module: str) -> dict[str, Any]:
    runtime = _mapping(state.get("runtime"))
    snapshot = _mapping(state.get("runtime_snapshot"))
    freshness = _mapping(state.get("freshness"))
    decision = _mapping(state.get("decision_panel"))
    return {
        "source": runtime.get("source", snapshot.get("source", DATA_UNAVAILABLE)),
        "source_module": f"dashboard.mission_control.{source_module}",
        "provenance": snapshot.get("provenance", {}),
        "generated_at": state.get("generated_at", DATA_UNAVAILABLE),
        "freshness": freshness.get("overall_freshness", DATA_UNAVAILABLE),
        "runtime_id": runtime.get("runtime_id", snapshot.get("runtime_id", DATA_UNAVAILABLE)),
        "state_hash": runtime.get("state_hash", snapshot.get("state_hash", DATA_UNAVAILABLE)),
        "decision_hash": decision.get("state_hash", DATA_UNAVAILABLE),
    }


def _runtime_unavailable(state: Mapping[str, Any]) -> bool:
    runtime = _mapping(state.get("runtime"))
    return str(runtime.get("runtime_status", "")).upper() in {"OFFLINE", "UNAVAILABLE"} or str(runtime.get("source", "")).upper() in {"", "UNAVAILABLE", "UNKNOWN"}


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


__all__ = ["build_institutional_executive_dashboard"]
