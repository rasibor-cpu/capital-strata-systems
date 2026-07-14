from __future__ import annotations

from collections.abc import MutableSequence
from typing import Any, Mapping, Sequence

from backend.options.options_income_enterprise_adapter import (
    ENTERPRISE_SAFE_FLAGS,
    PAYLOAD_VERSION,
    SUBSYSTEM_ID,
    OptionsIncomeEnterpriseIntegrationError,
    assert_enterprise_safe,
    normalize_timestamp,
    stable_id,
)


class OptionsIncomeAuditAdapter:
    def build_record(
        self,
        *,
        decision: str,
        inputs: Mapping[str, Any] | None,
        outputs: Mapping[str, Any] | None,
        rules_evaluated: Sequence[str] | None,
        timestamp: str,
        source_modules: Sequence[str] | None = None,
        correlation_id: str | None = None,
        warnings: Sequence[Any] | None = None,
        failures: Sequence[Any] | None = None,
        unavailable_data: Sequence[Any] | None = None,
        certification_evidence: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        when = normalize_timestamp(timestamp)
        payload_inputs = dict(inputs or {})
        payload_outputs = dict(outputs or {})
        assert_enterprise_safe({**payload_inputs, **ENTERPRISE_SAFE_FLAGS})
        assert_enterprise_safe({**payload_outputs, **ENTERPRISE_SAFE_FLAGS})
        corr = str(correlation_id or stable_id("oi-audit-correlation", decision, when))
        record = {
            "audit_id": stable_id("oi-audit", decision, corr, when, payload_outputs),
            "payload_version": PAYLOAD_VERSION,
            "subsystem": SUBSYSTEM_ID,
            "decision": str(decision or "UNKNOWN").upper(),
            "inputs": payload_inputs,
            "outputs": payload_outputs,
            "rules_evaluated": [str(item) for item in (rules_evaluated or [])],
            "supporting_metrics": _supporting_metrics(payload_outputs),
            "warnings": [str(item) for item in (warnings or [])],
            "failures": [str(item) for item in (failures or [])],
            "unavailable_data": [str(item) for item in (unavailable_data or [])],
            "source_modules": sorted(str(item) for item in (source_modules or [])),
            "correlation_id": corr,
            "certification_evidence": dict(certification_evidence or {}),
            "timestamp": when,
            "immutable": True,
            "append_only": True,
            "contains_sensitive_data": False,
            "broker_state_mutation": False,
            **ENTERPRISE_SAFE_FLAGS,
        }
        assert_enterprise_safe(record)
        return record

    def append(self, store: MutableSequence[Mapping[str, Any]] | None, record: Mapping[str, Any]) -> dict[str, Any]:
        if store is None:
            raise OptionsIncomeEnterpriseIntegrationError("missing audit framework")
        payload = dict(record)
        assert_enterprise_safe(payload)
        audit_id = str(payload.get("audit_id") or "")
        if not audit_id:
            raise OptionsIncomeEnterpriseIntegrationError("missing audit ID")
        if any(str(existing.get("audit_id")) == audit_id for existing in store if isinstance(existing, Mapping)):
            return payload
        store.append(payload)
        return payload


def build_options_income_audit_record(**kwargs: Any) -> dict[str, Any]:
    return OptionsIncomeAuditAdapter().build_record(**kwargs)


def append_options_income_audit_record(store: MutableSequence[Mapping[str, Any]] | None, record: Mapping[str, Any]) -> dict[str, Any]:
    return OptionsIncomeAuditAdapter().append(store, record)


def _supporting_metrics(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if key.endswith("_score") or key.endswith("_status") or key in {"risk_score", "readiness_score", "certification_score"}
    }


__all__ = ["OptionsIncomeAuditAdapter", "append_options_income_audit_record", "build_options_income_audit_record"]
