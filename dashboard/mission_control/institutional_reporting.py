from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dashboard.runtime.frontend_contract import DATA_UNAVAILABLE


def build_institutional_reporting(state: Mapping[str, Any]) -> dict[str, Any]:
    executive = _mapping(state.get("institutional_executive_dashboard"))
    risk = _mapping(state.get("risk_committee"))
    capital = _mapping(state.get("capital_committee"))
    broker = _mapping(state.get("broker_telemetry"))
    performance = _mapping(state.get("performance_attribution"))
    return {
        "status": "FAIL_CLOSED" if _runtime_unavailable(state) else executive.get("status", DATA_UNAVAILABLE),
        "summaries": [
            _summary("Daily CIO Summary", {"platform_health": executive.get("platform_health"), "top_alerts": executive.get("top_alerts", [])}),
            _summary("Risk Summary", {"risk_posture": risk.get("risk_posture"), "breaches": risk.get("breaches", [])}),
            _summary("Capital Summary", {"capital_efficiency": capital.get("capital_efficiency"), "unused_capital": capital.get("unused_capital")}),
            _summary("Broker Summary", {"broker_quality": broker.get("connection_status"), "market_data": broker.get("market_data")}),
            _summary("Performance Summary", {"pnl_attribution": performance.get("pnl_attribution"), "strategy_attribution": performance.get("strategy_attribution")}),
        ],
        "export_controls": "NOT_AVAILABLE_READ_ONLY",
        "links": _links("executive_overview", "documentation_runbooks", "audit_explainability"),
        "read_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
        **_metadata(state, "institutional_reporting"),
    }


def _summary(title: str, evidence: Mapping[str, Any]) -> dict[str, Any]:
    return {"title": title, "evidence": dict(evidence), "authority": "ADVISORY_ONLY"}


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


__all__ = ["build_institutional_reporting"]
