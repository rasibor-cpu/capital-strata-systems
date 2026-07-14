from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha256
from math import isfinite
from typing import Any, Mapping, Sequence

from backend.options.paper_position_repository import SAFE_FLAGS


PAYLOAD_VERSION = "css.ei001.options_income.enterprise.v1"
SUBSYSTEM_ID = "OPTIONS_INCOME"
SUBSYSTEM_NAME = "Options Income Engine"
SUBSYSTEM_VERSION = "EI-001"
CERTIFICATION_STATES = {
    "NOT_REGISTERED",
    "REGISTERED_PENDING_CERTIFICATION",
    "PAPER_CERTIFIED",
    "INTEGRATION_WARNING",
    "INTEGRATION_FAILED",
}
OPERATIONAL_STATES = {"ONLINE", "DEGRADED", "OFFLINE", "UNAVAILABLE"}
ENTERPRISE_SAFE_FLAGS = {"paper_only": True, **SAFE_FLAGS}


class OptionsIncomeEnterpriseIntegrationError(ValueError):
    """Raised when EI-001 enterprise integration must fail closed."""


def assert_enterprise_safe(payload: Mapping[str, Any], *, recursive: bool = True) -> None:
    if not isinstance(payload, Mapping):
        raise OptionsIncomeEnterpriseIntegrationError("integration payload must be a mapping")
    _assert_posture(payload)
    if recursive:
        _walk_payload(payload)


def build_fail_closed(reason: str, *, timestamp: str | None = None, section: str = "enterprise_integration") -> dict[str, Any]:
    return {
        "payload_version": PAYLOAD_VERSION,
        "section": section,
        "subsystem_id": SUBSYSTEM_ID,
        "subsystem_name": SUBSYSTEM_NAME,
        "timestamp": normalize_timestamp(timestamp),
        "status": "INTEGRATION_FAILED",
        "health": "OFFLINE",
        "readiness": "INTEGRATION_FAILED",
        "failure_reason": str(reason or "integration_failed"),
        "blockers": [str(reason or "integration_failed")],
        **ENTERPRISE_SAFE_FLAGS,
    }


def build_enterprise_operational_snapshot(
    *,
    runtime_registration: Mapping[str, Any] | None = None,
    dashboard: Mapping[str, Any] | None = None,
    risk: Mapping[str, Any] | None = None,
    alerts: Sequence[Mapping[str, Any]] | None = None,
    certification: Mapping[str, Any] | None = None,
    events: Sequence[Mapping[str, Any]] | None = None,
    audit_records: Sequence[Mapping[str, Any]] | None = None,
    learning_feedback: Sequence[Mapping[str, Any]] | None = None,
    timestamp: str | None = None,
    stale_after_seconds: int = 900,
) -> dict[str, Any]:
    generated_at = normalize_timestamp(timestamp)
    runtime_payload = _mapping(runtime_registration)
    dashboard_payload = _mapping(dashboard)
    risk_payload = _mapping(risk)
    certification_payload = _mapping(certification)
    alert_rows = [_mapping(row) for row in (alerts or [])]
    event_rows = [_mapping(row) for row in (events or [])]
    audit_rows = [_mapping(row) for row in (audit_records or [])]
    learning_rows = [_mapping(row) for row in (learning_feedback or [])]

    for payload in (runtime_payload, dashboard_payload, risk_payload, certification_payload):
        if payload:
            assert_enterprise_safe(payload)
    for row in alert_rows + event_rows + audit_rows + learning_rows:
        if row:
            assert_enterprise_safe(row)

    certification_state = _certification_state(certification_payload, runtime_payload)
    data_freshness = _freshness(dashboard_payload, generated_at, stale_after_seconds)
    critical_alerts = [row for row in alert_rows if str(row.get("severity", "")).upper() == "CRITICAL"]
    failures = []
    failures.extend(str(item) for item in runtime_payload.get("blockers", []) if item)
    failures.extend(str(item) for item in certification_payload.get("failures", certification_payload.get("blockers", [])) if item)
    failures.extend(str(item) for item in risk_payload.get("limit_breaches", []) if item)
    if certification_state == "INTEGRATION_FAILED":
        failures.append("certification_not_registered_or_failed")
    if data_freshness["status"] == "STALE":
        failures.append("stale_data")
    status = "OFFLINE" if failures else ("DEGRADED" if critical_alerts or certification_state == "INTEGRATION_WARNING" else "ONLINE")

    snapshot = {
        "payload_version": PAYLOAD_VERSION,
        "snapshot_id": stable_id("oi-enterprise-snapshot", generated_at, runtime_payload, certification_payload),
        "subsystem_id": SUBSYSTEM_ID,
        "subsystem_name": SUBSYSTEM_NAME,
        "timestamp": generated_at,
        "mode": "PAPER",
        "health": status,
        "readiness": certification_state,
        "certification_state": certification_state,
        "runtime": runtime_payload,
        "portfolio_summary": _dashboard_section(dashboard_payload, "portfolio"),
        "risk_summary": risk_payload,
        "alert_summary": {
            "total": len(alert_rows),
            "critical": len(critical_alerts),
            "warnings": sum(1 for row in alert_rows if str(row.get("severity", "")).upper() == "WARNING"),
            "informational": sum(1 for row in alert_rows if str(row.get("severity", "")).upper() in {"INFO", "INFORMATIONAL"}),
        },
        "certification_summary": certification_payload,
        "data_freshness": data_freshness,
        "event_status": _collection_status(event_rows),
        "audit_status": _collection_status(audit_rows),
        "dashboard_status": "ONLINE" if dashboard_payload else "UNAVAILABLE",
        "learning_feedback_status": _collection_status(learning_rows),
        "enterprise_integration_status": status,
        "blockers": sorted(set(failures)),
        "warnings": _warnings(runtime_payload, risk_payload, certification_payload, data_freshness),
        **ENTERPRISE_SAFE_FLAGS,
    }
    assert_enterprise_safe(snapshot)
    return _json_safe(snapshot)


def build_enterprise_risk_contribution(
    risk_assessment: Mapping[str, Any],
    *,
    portfolio: Mapping[str, Any] | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    risk = _mapping(risk_assessment)
    portfolio_payload = _mapping(portfolio)
    assert_enterprise_safe({**risk, **ENTERPRISE_SAFE_FLAGS})
    greeks = _mapping(risk.get("greeks_summary"))
    greeks_portfolio = _mapping(greeks.get("portfolio", greeks))
    assignment = _mapping(risk.get("assignment_summary", risk.get("assignment_exposure")))
    capital = _mapping(portfolio_payload.get("capital"))
    contribution = {
        "payload_version": PAYLOAD_VERSION,
        "risk_contribution_id": stable_id("oi-risk", risk, portfolio_payload),
        "timestamp": normalize_timestamp(timestamp),
        "asset_class": "OPTIONS",
        "subsystem": SUBSYSTEM_ID,
        "portfolio_delta": numeric(greeks_portfolio.get("delta", greeks_portfolio.get("portfolio_delta", 0.0)), "portfolio_delta"),
        "absolute_delta": numeric(greeks_portfolio.get("absolute_delta_exposure", greeks_portfolio.get("absolute_delta", 0.0)), "absolute_delta"),
        "gamma": numeric(greeks_portfolio.get("gamma", 0.0), "gamma"),
        "theta": numeric(greeks_portfolio.get("theta", 0.0), "theta"),
        "vega": numeric(greeks_portfolio.get("vega", 0.0), "vega"),
        "rho": numeric(greeks_portfolio.get("rho", 0.0), "rho"),
        "collateral_utilization": numeric(capital.get("portfolio_utilization", portfolio_payload.get("portfolio_utilization", 0.0)), "collateral_utilization"),
        "assignment_exposure": assignment,
        "concentration": _mapping(portfolio_payload.get("diversification")),
        "stressed_loss": numeric(_mapping(risk.get("stress_summary")).get("max_estimated_loss", risk.get("estimated_stressed_loss", 0.0)), "stressed_loss"),
        "risk_status": str(risk.get("portfolio_risk_status", risk.get("risk_status", "UNAVAILABLE"))).upper(),
        "approval_status": str(risk.get("approval_status", "REJECTED_INVALID_DATA")).upper(),
        "limit_breaches": list(risk.get("limit_breaches", risk.get("hard_limit_breaches", []))) if isinstance(risk.get("limit_breaches", risk.get("hard_limit_breaches", [])), list) else [],
        "warnings": list(risk.get("warnings", [])) if isinstance(risk.get("warnings", []), list) else [],
        "unavailable_data": list(risk.get("unavailable_data", risk.get("unavailable_risk_data", []))) if isinstance(risk.get("unavailable_data", risk.get("unavailable_risk_data", [])), list) else [],
        **ENTERPRISE_SAFE_FLAGS,
    }
    assert_enterprise_safe(contribution)
    return contribution


def normalize_timestamp(value: Any | None = None) -> str:
    if value in (None, ""):
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    raw = str(value).strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise OptionsIncomeEnterpriseIntegrationError("malformed timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.isoformat()


def stable_id(prefix: str, *parts: Any) -> str:
    digest = sha256(_stable_json(parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def numeric(value: Any, field: str, *, default: float | None = None) -> float:
    if value in (None, "") and default is not None:
        return default
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise OptionsIncomeEnterpriseIntegrationError(f"invalid numeric value: {field}") from exc
    if not isfinite(result):
        raise OptionsIncomeEnterpriseIntegrationError(f"non-finite numeric value: {field}")
    return result


def _assert_posture(payload: Mapping[str, Any]) -> None:
    for key, expected in ENTERPRISE_SAFE_FLAGS.items():
        if key in payload and payload.get(key) is not expected:
            raise OptionsIncomeEnterpriseIntegrationError(f"unsafe posture: {key}")
    if payload.get("mode") and str(payload.get("mode")).strip().upper() not in {"PAPER", "READ_ONLY", "ADVISORY"}:
        raise OptionsIncomeEnterpriseIntegrationError("live mode is rejected")


def _walk_payload(value: Any) -> None:
    if isinstance(value, Mapping):
        _assert_posture(value)
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in {"place_order", "submit_order", "cancel_order", "enable_live", "arm_execution"}:
                raise OptionsIncomeEnterpriseIntegrationError("order-capable payload rejected")
            if lowered in {"order_capable", "broker_write_capable", "supports_order_submission"} and item is True:
                raise OptionsIncomeEnterpriseIntegrationError("broker-write capability rejected")
            _walk_payload(item)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            _walk_payload(item)
    elif isinstance(value, float) and not isfinite(value):
        raise OptionsIncomeEnterpriseIntegrationError("non-finite numeric value")


def _certification_state(certification: Mapping[str, Any], runtime: Mapping[str, Any]) -> str:
    raw = str(
        certification.get("certification_state")
        or certification.get("overall_readiness")
        or certification.get("certification_status")
        or runtime.get("certification_status")
        or "NOT_REGISTERED"
    ).upper()
    if raw in {"PASS", "READY_FOR_CONTROLLED_CERTIFICATION", "READY_FOR_PAPER", "PAPER_CERTIFIED"}:
        return "PAPER_CERTIFIED"
    if raw in {"WARNING", "PASS_WITH_WARNINGS", "INTEGRATION_WARNING"}:
        return "INTEGRATION_WARNING"
    if raw in {"FAIL", "FAILED", "NOT_READY", "INTEGRATION_FAILED"}:
        return "INTEGRATION_FAILED"
    if raw in CERTIFICATION_STATES:
        return raw
    return "REGISTERED_PENDING_CERTIFICATION" if certification or runtime else "NOT_REGISTERED"


def _freshness(dashboard: Mapping[str, Any], timestamp: str, stale_after_seconds: int) -> dict[str, Any]:
    summary = _mapping(dashboard.get("summary"))
    last_update = summary.get("last_update") or dashboard.get("generated_at") or timestamp
    normalized = normalize_timestamp(last_update)
    age = max(0.0, (datetime.fromisoformat(timestamp) - datetime.fromisoformat(normalized)).total_seconds())
    return {
        "status": "STALE" if age > max(0, int(stale_after_seconds)) else "FRESH",
        "last_update": normalized,
        "age_seconds": round(age, 3),
        "stale_after_seconds": max(0, int(stale_after_seconds)),
        **ENTERPRISE_SAFE_FLAGS,
    }


def _dashboard_section(payload: Mapping[str, Any], section: str) -> dict[str, Any]:
    value = payload.get(section, {})
    return dict(value) if isinstance(value, Mapping) else {}


def _collection_status(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {"status": "ONLINE" if rows else "UNAVAILABLE", "count": len(rows), **ENTERPRISE_SAFE_FLAGS}


def _warnings(*payloads: Mapping[str, Any]) -> list[str]:
    result: list[str] = []
    for payload in payloads:
        for key in ("warnings", "warning", "unavailable_data", "unavailable_inputs"):
            value = payload.get(key)
            if isinstance(value, list):
                result.extend(str(item) for item in value)
            elif value:
                result.append(str(value))
    return sorted(set(result))


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _stable_json(value: Any) -> str:
    return json.dumps(_json_safe(value), sort_keys=True, separators=(",", ":"))


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise OptionsIncomeEnterpriseIntegrationError("non-finite numeric value")
        return value
    return str(value)


__all__ = [
    "CERTIFICATION_STATES",
    "ENTERPRISE_SAFE_FLAGS",
    "OPERATIONAL_STATES",
    "PAYLOAD_VERSION",
    "SUBSYSTEM_ID",
    "SUBSYSTEM_NAME",
    "SUBSYSTEM_VERSION",
    "OptionsIncomeEnterpriseIntegrationError",
    "assert_enterprise_safe",
    "build_enterprise_operational_snapshot",
    "build_enterprise_risk_contribution",
    "build_fail_closed",
    "normalize_timestamp",
    "numeric",
    "stable_id",
]
