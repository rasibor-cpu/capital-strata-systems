from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dashboard.runtime.frontend_contract import DATA_UNAVAILABLE


def build_audit_console(state: Mapping[str, Any]) -> dict[str, Any]:
    audit = _mapping(state.get("audit"))
    timeline = _mapping(state.get("operations_timeline"))
    certification = _mapping(state.get("certification"))
    committee = _mapping(state.get("committee_view"))
    decision = _mapping(state.get("decision_panel"))
    return {
        "status": "fail_closed" if _runtime_unavailable(state) else "available",
        "configuration_changes": _audit_list(audit, "configuration_changes"),
        "runtime_events": timeline.get("events", []),
        "operator_actions": audit.get("operator_actions", DATA_UNAVAILABLE),
        "certification_events": certification.get("blockers", []),
        "committee_actions": committee.get("committees", []),
        "decision_history": decision.get("decisions", []),
        "deletion_enabled": False,
        "read_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
        **_metadata(state, "audit_console"),
    }


def _audit_list(audit: Mapping[str, Any], key: str) -> list[Any]:
    evidence = _mapping(audit.get("audit_evidence"))
    value = evidence.get(key)
    return value if isinstance(value, list) else []


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
        "runtime_id": runtime.get("runtime_id", snapshot.get("runtime_id", DATA_UNAVAILABLE)),
        "state_hash": runtime.get("state_hash", snapshot.get("state_hash", DATA_UNAVAILABLE)),
    }


def _runtime_unavailable(state: Mapping[str, Any]) -> bool:
    runtime = _mapping(state.get("runtime"))
    return str(runtime.get("runtime_status", "")).upper() in {"OFFLINE", "UNAVAILABLE"} or str(runtime.get("source", "")).upper() in {"", "UNAVAILABLE", "UNKNOWN"}


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


__all__ = ["build_audit_console"]
