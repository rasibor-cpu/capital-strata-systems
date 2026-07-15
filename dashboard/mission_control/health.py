from __future__ import annotations

from collections.abc import Mapping
from typing import Any


HEALTH_GREEN = "GREEN"
HEALTH_AMBER = "AMBER"
HEALTH_RED = "RED"
HEALTH_UNAVAILABLE = "UNAVAILABLE"
HEALTH_FAIL_CLOSED = "FAIL_CLOSED"


def build_health_summary(
    state: Mapping[str, Any],
    *,
    freshness_summary: Mapping[str, Any],
) -> dict[str, Any]:
    reasons: list[str] = []
    safety = state.get("safety") if isinstance(state.get("safety"), Mapping) else {}
    validation = state.get("contract_validation") if isinstance(state.get("contract_validation"), Mapping) else {}

    if safety.get("execution_allowed") is not False:
        reasons.append("unsafe_execution_allowed")
    if safety.get("live_trading_blocked") is not True:
        reasons.append("unsafe_live_trading_not_blocked")
    if safety.get("broker_execution_armed") is not False:
        reasons.append("unsafe_broker_execution_armed")
    if safety.get("advisory_only") is not True:
        reasons.append("unsafe_advisory_only_missing")
    if validation and validation.get("valid") is not True:
        reasons.append("contract_validation_failed")
    if freshness_summary.get("stale_mandatory_data") is True:
        reasons.append("mandatory_data_stale")
    runtime_snapshot = state.get("runtime_snapshot") if isinstance(state.get("runtime_snapshot"), Mapping) else {}
    heartbeat_status = str(runtime_snapshot.get("heartbeat_status", "")).upper()
    if heartbeat_status in {"STALE", "OFFLINE", "UNAVAILABLE", "UNKNOWN"}:
        reasons.append("runtime_heartbeat_stale")
    if runtime_snapshot.get("runtime_status") in {"OFFLINE", "UNAVAILABLE"}:
        reasons.append("runtime_offline")

    broker = state.get("brokers") if isinstance(state.get("brokers"), Mapping) else {}
    active_broker = broker.get("active_broker") if isinstance(broker.get("active_broker"), Mapping) else {}
    broker_health = str(active_broker.get("connection_status") or active_broker.get("readiness") or "").upper()
    if broker_health in {"FAIL", "FAILED", "RED", "BROKER_UNAVAILABLE", "UNAVAILABLE"}:
        reasons.append("broker_state_not_green")

    if any(reason.startswith("unsafe_") for reason in reasons) or "contract_validation_failed" in reasons:
        health = HEALTH_FAIL_CLOSED
    elif "mandatory_data_stale" in reasons or "runtime_heartbeat_stale" in reasons:
        health = HEALTH_RED
    elif "runtime_offline" in reasons:
        health = HEALTH_UNAVAILABLE
    elif not state:
        health = HEALTH_UNAVAILABLE
    elif reasons:
        health = HEALTH_AMBER
    else:
        health = HEALTH_GREEN

    return {
        "health": health,
        "reasons": sorted(set(reasons)),
        "freshness": freshness_summary.get("overall_freshness", "UNKNOWN"),
        "read_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }


__all__ = [
    "HEALTH_AMBER",
    "HEALTH_FAIL_CLOSED",
    "HEALTH_GREEN",
    "HEALTH_RED",
    "HEALTH_UNAVAILABLE",
    "build_health_summary",
]
