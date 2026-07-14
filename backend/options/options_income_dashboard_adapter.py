from __future__ import annotations

from typing import Any, Callable, Mapping

from backend.options.options_income_enterprise_adapter import (
    ENTERPRISE_SAFE_FLAGS,
    PAYLOAD_VERSION,
    SUBSYSTEM_ID,
    OptionsIncomeEnterpriseIntegrationError,
    assert_enterprise_safe,
    normalize_timestamp,
)


PANELS = (
    "summary",
    "opportunities",
    "positions",
    "rolls",
    "portfolio",
    "income_targets",
    "greeks",
    "risk_budgets",
    "risk_limits",
    "assignment_exposure",
    "volatility_risk",
    "stress_tests",
    "alerts",
    "certification",
    "runtime_health",
    "operational_readiness",
)


class OptionsIncomeDashboardAdapter:
    def register(self, registry: dict[str, Any] | None, *, payload_provider: Callable[[], Mapping[str, Any]] | None = None) -> dict[str, Any]:
        if registry is None:
            raise OptionsIncomeEnterpriseIntegrationError("missing dashboard framework")
        registration = {
            "payload_version": PAYLOAD_VERSION,
            "subsystem": SUBSYSTEM_ID,
            "panels": list(PANELS),
            "read_only": True,
            "server_created": False,
            "order_entry_controls": False,
            "payload_provider_registered": payload_provider is not None,
            **ENTERPRISE_SAFE_FLAGS,
        }
        existing = registry.get(SUBSYSTEM_ID)
        if existing is not None and dict(existing) != registration:
            raise OptionsIncomeEnterpriseIntegrationError("duplicate dashboard registration")
        registry[SUBSYSTEM_ID] = dict(registration)
        return registration

    def build_enterprise_payload(
        self,
        dashboard_payload: Mapping[str, Any],
        *,
        certification: Mapping[str, Any] | None = None,
        runtime_registration: Mapping[str, Any] | None = None,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        root = dict(dashboard_payload)
        assert_enterprise_safe(root)
        generated_at = normalize_timestamp(timestamp or root.get("generated_at"))
        panels = {
            "summary": dict(root.get("summary", {})),
            "opportunities": dict(root.get("opportunities", {})),
            "positions": dict(root.get("positions", {})),
            "rolls": dict(root.get("rolls", {})),
            "portfolio": dict(root.get("portfolio", {})),
            "income_targets": dict(dict(root.get("portfolio", {})).get("income_targets", {})),
            "greeks": dict(root.get("greeks", {})),
            "risk_budgets": dict(dict(root.get("risk", {})).get("risk_budgets", {})),
            "risk_limits": {
                "limit_breaches": list(dict(root.get("risk", {})).get("limit_breaches", [])),
                "approval_status": dict(root.get("risk", {})).get("approval_status"),
                **ENTERPRISE_SAFE_FLAGS,
            },
            "assignment_exposure": dict(dict(root.get("risk", {})).get("assignment_exposure", {})),
            "volatility_risk": dict(dict(root.get("risk", {})).get("volatility_risk", {})),
            "stress_tests": dict(root.get("stress_tests", {})),
            "alerts": list(root.get("alerts", [])),
            "certification": dict(certification or {}),
            "runtime_health": dict(runtime_registration or {}),
            "operational_readiness": dict(root.get("operational_status", {})),
        }
        payload = {
            "payload_version": PAYLOAD_VERSION,
            "subsystem": SUBSYSTEM_ID,
            "generated_at": generated_at,
            "read_only": True,
            "sections": panels,
            "panel_order": list(PANELS),
            "dashboard_contract_preserved": True,
            **ENTERPRISE_SAFE_FLAGS,
        }
        assert_enterprise_safe(payload)
        return payload


def register_options_income_dashboard(registry: dict[str, Any] | None, **kwargs: Any) -> dict[str, Any]:
    return OptionsIncomeDashboardAdapter().register(registry, **kwargs)


def build_options_income_enterprise_dashboard(dashboard_payload: Mapping[str, Any], **kwargs: Any) -> dict[str, Any]:
    return OptionsIncomeDashboardAdapter().build_enterprise_payload(dashboard_payload, **kwargs)


__all__ = [
    "PANELS",
    "OptionsIncomeDashboardAdapter",
    "build_options_income_enterprise_dashboard",
    "register_options_income_dashboard",
]
