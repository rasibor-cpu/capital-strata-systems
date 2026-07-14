from __future__ import annotations

from typing import Any, Mapping

from backend.options.options_income_enterprise_adapter import (
    ENTERPRISE_SAFE_FLAGS,
    PAYLOAD_VERSION,
    SUBSYSTEM_ID,
    SUBSYSTEM_NAME,
    OptionsIncomeEnterpriseIntegrationError,
    assert_enterprise_safe,
    build_enterprise_operational_snapshot,
    normalize_timestamp,
)


RC1_RUNTIME_SNAPSHOT_VERSION = "css.rc1_oi.runtime_snapshot.v1"


def build_rc1_oi_runtime_snapshot(
    *,
    runtime_registration: Mapping[str, Any],
    operational_snapshot: Mapping[str, Any],
    timestamp: str,
) -> dict[str, Any]:
    registration = dict(runtime_registration)
    snapshot = dict(operational_snapshot)
    assert_enterprise_safe(registration)
    assert_enterprise_safe(snapshot)
    when = normalize_timestamp(timestamp)
    payload = {
        "payload_version": RC1_RUNTIME_SNAPSHOT_VERSION,
        "subsystem_id": SUBSYSTEM_ID,
        "subsystem_name": SUBSYSTEM_NAME,
        "timestamp": when,
        "runtime_status": snapshot.get("enterprise_integration_status", snapshot.get("health", "UNAVAILABLE")),
        "health": snapshot.get("health", "UNAVAILABLE"),
        "readiness": snapshot.get("readiness", "UNAVAILABLE"),
        "data_freshness": dict(snapshot.get("data_freshness", {})),
        "portfolio_summary": dict(snapshot.get("portfolio_summary", {})),
        "risk_status": dict(snapshot.get("risk_summary", {})).get("risk_status", "UNAVAILABLE"),
        "alert_summary": dict(snapshot.get("alert_summary", {})),
        "certification_status": snapshot.get("certification_state", "NOT_REGISTERED"),
        "integration_status": snapshot.get("enterprise_integration_status", "UNAVAILABLE"),
        "last_heartbeat": registration.get("last_heartbeat"),
        "last_assessment": when,
        "last_failure": registration.get("last_failure"),
        "failure_reason": registration.get("failure_reason"),
        **ENTERPRISE_SAFE_FLAGS,
    }
    assert_enterprise_safe(payload)
    return payload


def register_rc1_oi_runtime_snapshot(registry: dict[str, Any] | None, snapshot: Mapping[str, Any]) -> dict[str, Any]:
    if registry is None:
        raise OptionsIncomeEnterpriseIntegrationError("missing runtime snapshot contract")
    payload = dict(snapshot)
    assert_enterprise_safe(payload)
    key = str(payload.get("subsystem_id", "")).upper()
    if key != SUBSYSTEM_ID:
        raise OptionsIncomeEnterpriseIntegrationError("invalid subsystem identity")
    existing = registry.get(key)
    if existing is not None and dict(existing) != payload:
        raise OptionsIncomeEnterpriseIntegrationError("duplicate conflicting runtime snapshot")
    registry[key] = payload
    return payload


def build_operational_snapshot_from_ei001(**kwargs: Any) -> dict[str, Any]:
    return build_enterprise_operational_snapshot(**kwargs)


__all__ = [
    "RC1_RUNTIME_SNAPSHOT_VERSION",
    "build_operational_snapshot_from_ei001",
    "build_rc1_oi_runtime_snapshot",
    "register_rc1_oi_runtime_snapshot",
]
