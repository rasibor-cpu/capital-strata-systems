from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dashboard.runtime.frontend_contract import DATA_UNAVAILABLE


def build_governance_summary_console(state: Mapping[str, Any]) -> dict[str, Any]:
    safety = _mapping(state.get("safety"))
    audit = _mapping(state.get("audit_console"))
    approvals = _mapping(state.get("approval_workflow_console"))
    config = _mapping(state.get("configuration_console"))
    certification = _mapping(state.get("certification"))
    return {
        "status": "fail_closed" if _runtime_unavailable(state) else "available",
        "security_posture": safety.get("safety_status", DATA_UNAVAILABLE),
        "audit_posture": audit.get("status", DATA_UNAVAILABLE),
        "approval_posture": approvals.get("status", DATA_UNAVAILABLE),
        "configuration_posture": config.get("status", DATA_UNAVAILABLE),
        "certification_posture": certification.get("rc1_platform_certification", DATA_UNAVAILABLE),
        "write_routes_enabled": False,
        "operator_actions_enabled": False,
        "read_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
        **_metadata(state, "governance_summary"),
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
        "runtime_id": runtime.get("runtime_id", snapshot.get("runtime_id", DATA_UNAVAILABLE)),
        "state_hash": runtime.get("state_hash", snapshot.get("state_hash", DATA_UNAVAILABLE)),
    }


def _runtime_unavailable(state: Mapping[str, Any]) -> bool:
    runtime = _mapping(state.get("runtime"))
    return str(runtime.get("runtime_status", "")).upper() in {"OFFLINE", "UNAVAILABLE"} or str(runtime.get("source", "")).upper() in {"", "UNAVAILABLE", "UNKNOWN"}


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


__all__ = ["build_governance_summary_console"]
