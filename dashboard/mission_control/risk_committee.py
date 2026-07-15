from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dashboard.runtime.frontend_contract import DATA_UNAVAILABLE


def build_risk_committee_panel(state: Mapping[str, Any]) -> dict[str, Any]:
    source = _mapping(state.get("risk_command_center"))
    risk = _mapping(state.get("risk"))
    return {
        "status": "FAIL_CLOSED" if _runtime_unavailable(state) else source.get("status", DATA_UNAVAILABLE),
        "risk_posture": source.get("status", risk.get("overall_risk_state", DATA_UNAVAILABLE)),
        "drawdown": source.get("drawdown", risk.get("drawdown", DATA_UNAVAILABLE)),
        "concentration": risk.get("concentration", DATA_UNAVAILABLE),
        "var": source.get("var", DATA_UNAVAILABLE),
        "stress": source.get("stress_metrics", risk.get("stress_tests", DATA_UNAVAILABLE)),
        "anti_bleed_guard": source.get("anti_bleed_guard", DATA_UNAVAILABLE),
        "kill_switch": source.get("kill_switch", DATA_UNAVAILABLE),
        "breaches": risk.get("limit_breaches", []),
        "warnings": risk.get("warnings", []),
        "links": _links("risk_command", "portfolio", "certification_readiness"),
        "read_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
        **_metadata(state, "risk_committee"),
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


__all__ = ["build_risk_committee_panel"]
