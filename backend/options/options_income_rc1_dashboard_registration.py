from __future__ import annotations

from typing import Any, Mapping

from backend.options.options_income_dashboard_adapter import PANELS, build_options_income_enterprise_dashboard, register_options_income_dashboard
from backend.options.options_income_enterprise_adapter import (
    ENTERPRISE_SAFE_FLAGS,
    SUBSYSTEM_ID,
    OptionsIncomeEnterpriseIntegrationError,
    assert_enterprise_safe,
)


RC1_DASHBOARD_VERSION = "css.rc1_oi.dashboard_host.v1"


def consume_rc1_oi_dashboard_host(
    dashboard_host: dict[str, Any] | None,
    *,
    dashboard_payload: Mapping[str, Any],
    certification: Mapping[str, Any] | None = None,
    runtime_registration: Mapping[str, Any] | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    if dashboard_host is None:
        raise OptionsIncomeEnterpriseIntegrationError("missing dashboard host")
    registration = register_options_income_dashboard(dashboard_host, payload_provider=lambda: dashboard_payload)
    enterprise_payload = build_options_income_enterprise_dashboard(
        dashboard_payload,
        certification=certification,
        runtime_registration=runtime_registration,
        timestamp=timestamp,
    )
    payload = {
        "payload_version": RC1_DASHBOARD_VERSION,
        "subsystem": SUBSYSTEM_ID,
        "host_registration": registration,
        "panels": list(PANELS),
        "enterprise_payload": enterprise_payload,
        "mobile_host_supported": True,
        "order_entry_controls": False,
        "trade_buttons": False,
        **ENTERPRISE_SAFE_FLAGS,
    }
    assert_enterprise_safe(payload)
    return payload


__all__ = ["RC1_DASHBOARD_VERSION", "consume_rc1_oi_dashboard_host"]
