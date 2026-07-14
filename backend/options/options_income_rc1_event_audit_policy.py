from __future__ import annotations

from typing import Any, Mapping, Sequence

from backend.options.options_income_audit_adapter import append_options_income_audit_record
from backend.options.options_income_enterprise_adapter import (
    ENTERPRISE_SAFE_FLAGS,
    PAYLOAD_VERSION,
    SUBSYSTEM_ID,
    OptionsIncomeEnterpriseIntegrationError,
    assert_enterprise_safe,
)
from backend.options.options_income_event_adapter import EVENT_TYPES, publish_options_income_events


PERSISTED_EVENT_TYPES = (
    "PAPER_POSITION_CREATED",
    "PAPER_POSITION_UPDATED",
    "PAPER_POSITION_COMPLETED",
    "PORTFOLIO_CONSTRUCTED",
    "RISK_ASSESSMENT_COMPLETED",
    "RISK_LIMIT_BREACHED",
    "STRESS_TEST_COMPLETED",
    "ALERT_RAISED",
    "CERTIFICATION_COMPLETED",
    "READINESS_UPDATED",
)
TRANSIENT_EVENT_TYPES = tuple(item for item in EVENT_TYPES if item not in PERSISTED_EVENT_TYPES)
SENSITIVE_FIELDS = ("credential", "token", "private_key", "pem", "jwt", "account_secret", "api_key", "password")


def build_rc1_oi_event_policy(events: Sequence[Mapping[str, Any]], *, event_bus: Any) -> dict[str, Any]:
    if event_bus is None:
        raise OptionsIncomeEnterpriseIntegrationError("missing event bus")
    _assert_redacted(events)
    published = publish_options_income_events(events, event_bus)
    payload = {
        "payload_version": PAYLOAD_VERSION,
        "subsystem": SUBSYSTEM_ID,
        "status": "PASS",
        "persisted_event_types": list(PERSISTED_EVENT_TYPES),
        "transient_event_types": list(TRANSIENT_EVENT_TYPES),
        "event_count": len(published),
        "retention_metadata": {"retention_class": "rc1_options_income", "append_only": True, "replayable": True},
        "idempotency_keys": [event["event_id"] for event in published],
        "correlation_ids": sorted({event["correlation_id"] for event in published}),
        "schema_versions": sorted({event["payload_version"] for event in published}),
        "redaction_rules": list(SENSITIVE_FIELDS),
        "replay_behavior": "deterministic_stable_id_replay",
        "restart_behavior": "safe_republish_idempotent",
        "failure_handling": "fail_closed",
        **ENTERPRISE_SAFE_FLAGS,
    }
    assert_enterprise_safe(payload)
    return payload


def build_rc1_oi_audit_policy(records: Sequence[Mapping[str, Any]], *, audit_store: list[Mapping[str, Any]] | None) -> dict[str, Any]:
    if audit_store is None:
        raise OptionsIncomeEnterpriseIntegrationError("missing audit framework")
    _assert_redacted(records)
    appended = [append_options_income_audit_record(audit_store, record) for record in records]
    payload = {
        "payload_version": PAYLOAD_VERSION,
        "subsystem": SUBSYSTEM_ID,
        "status": "PASS",
        "audit_count": len(appended),
        "retention_metadata": {"retention_class": "rc1_options_income_audit", "immutable": True, "append_only": True},
        "idempotency_keys": [record["audit_id"] for record in appended],
        "correlation_ids": sorted({record.get("correlation_id", "") for record in appended}),
        "schema_versions": sorted({record.get("payload_version", PAYLOAD_VERSION) for record in appended}),
        "redaction_rules": list(SENSITIVE_FIELDS),
        "replay_behavior": "append_idempotent",
        "restart_behavior": "safe_reappend_idempotent",
        "failure_handling": "fail_closed",
        **ENTERPRISE_SAFE_FLAGS,
    }
    assert_enterprise_safe(payload)
    return payload


def _assert_redacted(values: Any) -> None:
    if isinstance(values, Mapping):
        for key, value in values.items():
            lowered = str(key).lower()
            if any(field in lowered for field in SENSITIVE_FIELDS):
                raise OptionsIncomeEnterpriseIntegrationError("sensitive field rejected")
            _assert_redacted(value)
    elif isinstance(values, (list, tuple, set)):
        for item in values:
            _assert_redacted(item)


__all__ = [
    "PERSISTED_EVENT_TYPES",
    "SENSITIVE_FIELDS",
    "TRANSIENT_EVENT_TYPES",
    "build_rc1_oi_audit_policy",
    "build_rc1_oi_event_policy",
]
