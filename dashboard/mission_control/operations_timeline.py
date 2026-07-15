from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from dashboard.runtime.frontend_contract import DATA_UNAVAILABLE


def build_operations_timeline(state: Mapping[str, Any]) -> dict[str, Any]:
    runtime = _mapping(state.get("runtime"))
    platform = _mapping(state.get("platform"))
    alerts = _mapping(state.get("alerts"))
    brokers = _mapping(state.get("brokers"))
    certification = _mapping(state.get("certification"))
    active_broker = _mapping(brokers.get("active_broker"))
    generated_at = str(state.get("generated_at") or _now())

    events = [
        _event(state, "runtime_startup", runtime.get("runtime_status"), runtime.get("heartbeat"), "runtime", "Runtime status observed"),
        _event(state, "heartbeat", runtime.get("heartbeat_status"), runtime.get("heartbeat"), "runtime", "Runtime heartbeat observed"),
        _event(state, "runtime_cycle", runtime.get("cycle"), runtime.get("heartbeat"), "runtime", "Runtime cycle observed"),
        _event(state, "broker_event", active_broker.get("connection_status"), runtime.get("heartbeat"), "broker", "Broker connection observed"),
        _event(state, "certification_event", certification.get("rc1_operational_readiness"), generated_at, "certification", "Certification state observed"),
    ]
    for alert in _list(alerts.get("active_alerts")):
        if isinstance(alert, Mapping):
            events.append(
                _event(
                    state,
                    "alert",
                    alert.get("severity", alerts.get("severity", "UNAVAILABLE")),
                    alert.get("timestamp", generated_at),
                    str(alert.get("category", "alerts")).lower(),
                    alert.get("message", "Alert observed"),
                )
            )
    if platform.get("runtime_offline"):
        events.append(_event(state, "runtime_warning", "UNAVAILABLE", generated_at, "runtime", "Runtime evidence unavailable"))

    return {
        "status": "UNAVAILABLE" if platform.get("runtime_offline") else "AVAILABLE",
        "events": sorted(events, key=lambda item: _sort_key(item.get("timestamp"))),
        "warnings": ["runtime_unavailable"] if platform.get("runtime_offline") else [],
        **_metadata(state, "operations_timeline"),
        "read_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }


def _event(state: Mapping[str, Any], event_type: str, status: Any, timestamp: Any, category: str, message: Any) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "category": category,
        "timestamp": timestamp or DATA_UNAVAILABLE,
        "status": status if status not in (None, "") else DATA_UNAVAILABLE,
        "message": message if message not in (None, "") else DATA_UNAVAILABLE,
        **_metadata(state, event_type),
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


def _sort_key(value: Any) -> str:
    text = str(value or "")
    return text if text and text != DATA_UNAVAILABLE else "9999"


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = ["build_operations_timeline"]
