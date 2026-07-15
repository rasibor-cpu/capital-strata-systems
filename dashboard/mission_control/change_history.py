from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dashboard.runtime.frontend_contract import DATA_UNAVAILABLE


def build_change_history_console(state: Mapping[str, Any]) -> dict[str, Any]:
    audit = _mapping(state.get("audit"))
    evidence = _mapping(audit.get("audit_evidence"))
    rows = evidence.get("change_history")
    changes = [_change(row) for row in rows] if isinstance(rows, list) else []
    return {
        "status": "fail_closed" if _runtime_unavailable(state) else "available",
        "changes": changes,
        "change_count": len(changes),
        "read_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
        **_metadata(state, "change_history"),
    }


def _change(row: Any) -> dict[str, Any]:
    payload = dict(row) if isinstance(row, Mapping) else {}
    return {
        "who": payload.get("who", DATA_UNAVAILABLE),
        "what": payload.get("what", DATA_UNAVAILABLE),
        "when": payload.get("when", DATA_UNAVAILABLE),
        "reason": payload.get("reason", DATA_UNAVAILABLE),
        "approval_status": payload.get("approval_status", DATA_UNAVAILABLE),
        "rollback_available": bool(payload.get("rollback_available", False)),
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


__all__ = ["build_change_history_console"]
