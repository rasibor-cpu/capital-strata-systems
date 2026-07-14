from __future__ import annotations

from typing import Any, Mapping, Sequence

from backend.monitoring.css_alert_models import AlertSeverity, AlertType
from backend.options.options_income_enterprise_adapter import (
    ENTERPRISE_SAFE_FLAGS,
    PAYLOAD_VERSION,
    SUBSYSTEM_ID,
    OptionsIncomeEnterpriseIntegrationError,
    assert_enterprise_safe,
    normalize_timestamp,
    stable_id,
)


SEVERITY_MAP = {"CRITICAL": AlertSeverity.CRITICAL.value, "WARNING": AlertSeverity.WARNING.value, "INFO": AlertSeverity.INFO.value}


class OptionsIncomeAlertAdapter:
    def adapt(self, alerts: Sequence[Mapping[str, Any]], *, timestamp: str | None = None) -> list[dict[str, Any]]:
        rows = []
        for alert in alerts:
            item = dict(alert)
            assert_enterprise_safe(item)
            severity = SEVERITY_MAP.get(str(item.get("severity", "INFO")).upper(), AlertSeverity.INFO.value)
            when = normalize_timestamp(item.get("timestamp") or timestamp)
            rows.append(
                {
                    "alert_id": str(item.get("alert_id") or stable_id("oi-alert", item, when)),
                    "payload_version": PAYLOAD_VERSION,
                    "subsystem": SUBSYSTEM_ID,
                    "alert_type": AlertType.RISK.value if item.get("category") in {"risk-limit", "assignment", "collateral"} else AlertType.SYSTEM.value,
                    "severity": severity,
                    "category": str(item.get("category", "options_income")),
                    "message": str(item.get("message", "Options income alert")),
                    "reason": str(item.get("reason", "")),
                    "supporting_metrics": dict(item.get("supporting_metrics", {})) if isinstance(item.get("supporting_metrics"), Mapping) else {},
                    "affected_entities": list(item.get("affected_entities", [])) if isinstance(item.get("affected_entities"), list) else [],
                    "timestamp": when,
                    "acknowledged": bool(item.get("acknowledged", False)),
                    "external_notification_sent": False,
                    **ENTERPRISE_SAFE_FLAGS,
                }
            )
        rows.sort(key=lambda row: ({"CRITICAL": 0, "WARNING": 1, "INFO": 2}.get(row["severity"], 9), row["category"], row["alert_id"]))
        ids = [row["alert_id"] for row in rows]
        if len(ids) != len(set(ids)):
            raise OptionsIncomeEnterpriseIntegrationError("duplicate alert IDs")
        return rows


def adapt_options_income_alerts(alerts: Sequence[Mapping[str, Any]], **kwargs: Any) -> list[dict[str, Any]]:
    return OptionsIncomeAlertAdapter().adapt(alerts, **kwargs)


__all__ = ["SEVERITY_MAP", "OptionsIncomeAlertAdapter", "adapt_options_income_alerts"]
