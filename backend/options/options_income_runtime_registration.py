from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any, Mapping

from backend.options.options_income_enterprise_adapter import (
    ENTERPRISE_SAFE_FLAGS,
    PAYLOAD_VERSION,
    SUBSYSTEM_ID,
    SUBSYSTEM_NAME,
    SUBSYSTEM_VERSION,
    OptionsIncomeEnterpriseIntegrationError,
    assert_enterprise_safe,
    build_fail_closed,
    normalize_timestamp,
)


CAPABILITIES = (
    "paper_strategy_domain",
    "paper_opportunity_scanning",
    "paper_lifecycle",
    "paper_position_management",
    "paper_portfolio_construction",
    "paper_risk_governance",
    "paper_dashboard_payloads",
    "paper_broker_abstraction",
    "paper_certification",
    "enterprise_integration_adapters",
)
DEPENDENCIES = (
    "backend.options.options_income_certification",
    "backend.options.options_income_dashboard",
    "backend.options.options_income_risk_governance",
    "backend.events.event_bus",
    "backend.certification.certification_engine",
)


class OptionsIncomeRuntimeRegistration:
    def build_registration(
        self,
        *,
        timestamp: str | None = None,
        health: str = "ONLINE",
        readiness: str = "REGISTERED_PENDING_CERTIFICATION",
        certification_status: str = "REGISTERED_PENDING_CERTIFICATION",
        last_success: str | None = None,
        last_failure: str | None = None,
        failure_reason: str | None = None,
    ) -> dict[str, Any]:
        generated_at = normalize_timestamp(timestamp)
        health_status = _status(health)
        registration = {
            "payload_version": PAYLOAD_VERSION,
            "subsystem_id": SUBSYSTEM_ID,
            "subsystem_name": SUBSYSTEM_NAME,
            "version": SUBSYSTEM_VERSION,
            "mode": "PAPER",
            "capabilities": sorted(CAPABILITIES),
            "dependencies": sorted(DEPENDENCIES),
            "health": health_status,
            "readiness": str(readiness or "REGISTERED_PENDING_CERTIFICATION").upper(),
            "last_heartbeat": generated_at,
            "last_success": normalize_timestamp(last_success or generated_at) if health_status in {"ONLINE", "DEGRADED"} else None,
            "last_failure": normalize_timestamp(last_failure) if last_failure else None,
            "failure_reason": str(failure_reason) if failure_reason else None,
            "certification_status": str(certification_status or "REGISTERED_PENDING_CERTIFICATION").upper(),
            "non_executable": True,
            "restart_safe": True,
            "idempotent": True,
            "deterministic": True,
            **ENTERPRISE_SAFE_FLAGS,
        }
        assert_enterprise_safe(registration)
        return registration

    def register(
        self,
        registry: MutableMapping[str, Mapping[str, Any]] | None,
        registration: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if registry is None:
            raise OptionsIncomeEnterpriseIntegrationError("missing enterprise registry")
        payload = dict(registration or self.build_registration())
        assert_enterprise_safe(payload)
        key = str(payload.get("subsystem_id") or "").upper()
        if key != SUBSYSTEM_ID:
            raise OptionsIncomeEnterpriseIntegrationError("invalid subsystem identity")
        existing = registry.get(key)
        if existing is not None:
            if dict(existing) == payload:
                return dict(existing)
            raise OptionsIncomeEnterpriseIntegrationError("duplicate subsystem registration")
        registry[key] = dict(payload)
        return dict(payload)


def build_options_income_runtime_registration(**kwargs: Any) -> dict[str, Any]:
    try:
        return OptionsIncomeRuntimeRegistration().build_registration(**kwargs)
    except Exception as exc:
        return build_fail_closed(str(exc), section="runtime_registration")


def register_options_income_runtime(
    registry: MutableMapping[str, Mapping[str, Any]] | None,
    registration: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return OptionsIncomeRuntimeRegistration().register(registry, registration)


def _status(value: str) -> str:
    status = str(value or "UNAVAILABLE").upper()
    if status not in {"ONLINE", "DEGRADED", "OFFLINE", "UNAVAILABLE"}:
        raise OptionsIncomeEnterpriseIntegrationError("invalid runtime health")
    return status


__all__ = [
    "CAPABILITIES",
    "DEPENDENCIES",
    "OptionsIncomeRuntimeRegistration",
    "build_options_income_runtime_registration",
    "register_options_income_runtime",
]
