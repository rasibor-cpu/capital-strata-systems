from __future__ import annotations

from typing import Any, Mapping, Sequence

from backend.events.event_models import Event
from backend.options.options_income_enterprise_adapter import (
    ENTERPRISE_SAFE_FLAGS,
    PAYLOAD_VERSION,
    SUBSYSTEM_ID,
    OptionsIncomeEnterpriseIntegrationError,
    assert_enterprise_safe,
    normalize_timestamp,
    stable_id,
)


EVENT_TYPES = (
    "OPPORTUNITY_ACCEPTED",
    "OPPORTUNITY_REJECTED",
    "PAPER_POSITION_CREATED",
    "PAPER_POSITION_UPDATED",
    "PAPER_POSITION_COMPLETED",
    "ROLL_RECOMMENDED",
    "PORTFOLIO_CONSTRUCTED",
    "PORTFOLIO_REBALANCE_RECOMMENDED",
    "RISK_ASSESSMENT_COMPLETED",
    "RISK_LIMIT_BREACHED",
    "STRESS_TEST_COMPLETED",
    "ALERT_RAISED",
    "CERTIFICATION_COMPLETED",
    "READINESS_UPDATED",
    "DASHBOARD_SNAPSHOT_GENERATED",
)


class OptionsIncomeEventAdapter:
    def build_event(
        self,
        event_type: str,
        *,
        entity_id: str,
        timestamp: str,
        source_module: str,
        payload: Mapping[str, Any] | None = None,
        correlation_id: str | None = None,
        severity: str = "INFO",
    ) -> dict[str, Any]:
        kind = str(event_type or "").upper()
        if kind not in EVENT_TYPES:
            raise OptionsIncomeEnterpriseIntegrationError("unsupported event type")
        when = normalize_timestamp(timestamp)
        corr = str(correlation_id or stable_id("oi-correlation", kind, entity_id, when))
        body = dict(payload or {})
        body.update(ENTERPRISE_SAFE_FLAGS)
        assert_enterprise_safe(body)
        event = {
            "event_id": stable_id("oi-event", kind, entity_id, source_module, when, corr),
            "event_type": kind,
            "subsystem": SUBSYSTEM_ID,
            "timestamp": when,
            "correlation_id": corr,
            "entity_id": str(entity_id or SUBSYSTEM_ID),
            "source_module": str(source_module or "backend.options"),
            "payload_version": PAYLOAD_VERSION,
            "severity": str(severity or "INFO").upper(),
            "category": "OPTIONS_INCOME",
            "payload": body,
            "audit_metadata": {
                "audit_category": "options_income_event",
                "immutable": True,
                "append_only": True,
                "broker_state_mutation": False,
                **ENTERPRISE_SAFE_FLAGS,
            },
            **ENTERPRISE_SAFE_FLAGS,
        }
        assert_enterprise_safe(event)
        return event

    def build_events(self, rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        events = [
            self.build_event(
                str(row.get("event_type")),
                entity_id=str(row.get("entity_id", SUBSYSTEM_ID)),
                timestamp=str(row.get("timestamp")),
                source_module=str(row.get("source_module", "backend.options")),
                payload=row.get("payload") if isinstance(row.get("payload"), Mapping) else {},
                correlation_id=str(row.get("correlation_id")) if row.get("correlation_id") else None,
                severity=str(row.get("severity", "INFO")),
            )
            for row in rows
        ]
        events.sort(key=lambda item: (EVENT_TYPES.index(item["event_type"]), item["entity_id"], item["event_id"]))
        ids = [item["event_id"] for item in events]
        if len(ids) != len(set(ids)):
            raise OptionsIncomeEnterpriseIntegrationError("duplicate event IDs")
        return events

    def publish(self, rows: Sequence[Mapping[str, Any]], event_bus: Any) -> list[dict[str, Any]]:
        if event_bus is None or not hasattr(event_bus, "publish"):
            raise OptionsIncomeEnterpriseIntegrationError("missing event bus")
        events = self.build_events(rows)
        for item in events:
            event = Event(
                event_type=item["event_type"],
                severity=item["severity"],
                category=item["category"],
                source=item["source_module"],
                payload=item,
                event_id=item["event_id"],
                timestamp=_epoch_seconds(item["timestamp"]),
                correlation_id=item["correlation_id"],
                schema_version="1.0.0",
            )
            event_bus.publish(event)
        return events


def build_options_income_events(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return OptionsIncomeEventAdapter().build_events(rows)


def publish_options_income_events(rows: Sequence[Mapping[str, Any]], event_bus: Any) -> list[dict[str, Any]]:
    return OptionsIncomeEventAdapter().publish(rows, event_bus)


def _epoch_seconds(timestamp: str) -> float:
    from datetime import datetime

    return datetime.fromisoformat(timestamp).timestamp()


__all__ = ["EVENT_TYPES", "OptionsIncomeEventAdapter", "build_options_income_events", "publish_options_income_events"]
