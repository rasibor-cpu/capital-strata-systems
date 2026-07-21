from __future__ import annotations

from collections.abc import Mapping
from typing import Any


SCHEMA_VERSION = "css.op002.canonical_broker_readiness.v1"
DATA_UNAVAILABLE = "DATA UNAVAILABLE"


def build_canonical_broker_readiness(
    *,
    broker_section: Mapping[str, Any] | None = None,
    runtime_snapshot: Mapping[str, Any] | None = None,
    certification_snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Project broker readiness from the canonical broker/runtime evidence."""

    broker = _mapping(broker_section)
    runtime = _mapping(runtime_snapshot)
    runtime_broker = _mapping(runtime.get("broker"))
    certification = _mapping(certification_snapshot or broker.get("runtime_certification_snapshot"))
    canonical = _mapping(broker.get("canonical_broker_runtime_state"))
    if not canonical and isinstance(certification.get("canonical_broker_runtime_state"), Mapping):
        canonical = _mapping(certification.get("canonical_broker_runtime_state"))

    source = canonical if canonical else runtime_broker if runtime_broker else broker
    selected_broker = _first(
        source.get("broker"),
        runtime_broker.get("selected_broker"),
        broker.get("selected_broker"),
        certification.get("broker"),
        default="NONE",
    )
    operational: dict[str, Any] = {}
    if str(selected_broker).upper() in {"COINBASE", "BINANCE", "OANDA", "QUESTRADE"}:
        from backend.app.brokers.operational_adapter import get_operational_adapter

        operational = get_operational_adapter(
            str(selected_broker),
            configuration=_mapping(source.get("configuration")),
            evidence=source,
        ).operational_snapshot()
    readiness = {
        "schema_version": SCHEMA_VERSION,
        "broker": str(selected_broker).upper(),
        "mode": _first(source.get("mode"), runtime_broker.get("broker_mode"), broker.get("broker_mode"), certification.get("mode"), default="paper"),
        "credential_status": _status(_first(source.get("credential_status"), broker.get("credential_status"), default="UNKNOWN")),
        "transport_status": _status(_first(source.get("transport_status"), runtime_broker.get("transport"), broker.get("connection_status"), default="UNKNOWN")),
        "authentication_status": _status(_first(source.get("authentication_status"), runtime_broker.get("authentication"), broker.get("authentication_status"), broker.get("auth_status"), default="NOT_TESTED")),
        "account_status": _status(_first(source.get("account_status"), runtime_broker.get("account"), broker.get("account_data_health"), default="UNAVAILABLE")),
        "balance_status": _status(_first(source.get("balance_status"), runtime_broker.get("balances"), broker.get("balance_position_status"), default="UNAVAILABLE")),
        "buying_power_status": _status(_first(source.get("buying_power_status"), runtime_broker.get("buying_power"), default="UNAVAILABLE")),
        "margin_status": _status(_first(source.get("margin_status"), runtime_broker.get("margin"), broker.get("margin_status"), default="UNAVAILABLE")),
        "market_data_status": _status(_first(source.get("market_data_status"), runtime_broker.get("market_data"), broker.get("market_data_status"), default="UNAVAILABLE")),
        "product_status": _status(_first(source.get("product_status"), runtime_broker.get("products"), broker.get("product_price_status"), default="UNAVAILABLE")),
        "latency_ms": _first(source.get("latency_ms"), broker.get("latency_ms"), certification.get("latency_ms"), default=DATA_UNAVAILABLE),
        "market_data_freshness": _mapping(certification.get("market_data_freshness")),
        "readiness_score": _number(_first(source.get("readiness_score"), broker.get("readiness_score"), certification.get("connectivity_score"), default=0.0)),
        "overall_status": _overall(_first(source.get("overall_status"), runtime_broker.get("overall_status"), broker.get("overall_status"), certification.get("certification"), default="UNAVAILABLE")),
        "failure_reason": _first(source.get("failure_reason"), runtime_broker.get("failure_reason"), broker.get("failure_reason"), default=DATA_UNAVAILABLE),
        "operational_state": operational.get("operational_state", "NOT_INITIALIZED"),
        "capability_states": operational.get("capability_states", {}),
        "expected_condition": operational.get("expected_condition", True),
        "retryable": operational.get("retryable", False),
        "recommended_action": operational.get("recommended_action", ""),
        "canonical_certification": operational.get("certification", "NOT_INITIALIZED"),
        "last_successful_operation": operational.get("last_successful_operation"),
        "warnings": _list(source.get("warning_reasons", runtime_broker.get("warnings", broker.get("readiness_reasons", [])))),
        "provenance": {
            "canonical_owner": "backend.runtime.broker_readiness_consolidation",
            "runtime_state_hash": runtime.get("state_hash", DATA_UNAVAILABLE),
            "broker_state_hash": _first(source.get("state_hash"), runtime_broker.get("state_hash"), broker.get("state_hash"), default=DATA_UNAVAILABLE),
            "source_modules": _list(source.get("source_modules")),
        },
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }
    readiness["ready_for_read_only_validation"] = (
        readiness["overall_status"] in {"GREEN", "AMBER"}
        and readiness["operational_state"] == "READ_ONLY_READY"
    )
    readiness["ready_for_execution"] = False
    return readiness


def _status(value: Any) -> str:
    text = str(value or "").strip().upper()
    if text in {"GREEN", "READY", "OK", "AVAILABLE", "AUTHENTICATED", "CONNECTED"}:
        return "PASS"
    if text in {"RED", "FAIL", "FAILED", "ERROR", "MISSING", "NOT_AUTHENTICATED"}:
        return "FAIL"
    if text in {"BLOCKED", "DISABLED"}:
        return "BLOCKED"
    if text in {"", "DATA UNAVAILABLE", "UNAVAILABLE", "NOT_AVAILABLE"}:
        return "UNAVAILABLE"
    return text


def _overall(value: Any) -> str:
    status = _status(value)
    if status == "PASS":
        return "GREEN"
    if status in {"WARNING", "WARN", "AMBER", "DEGRADED"}:
        return "AMBER"
    if status in {"FAIL", "BLOCKED"}:
        return "RED"
    return "UNAVAILABLE" if status in {"UNAVAILABLE", ""} else status


def _first(*values: Any, default: Any = "") -> Any:
    for value in values:
        if value not in (None, "", "UNKNOWN", DATA_UNAVAILABLE, "UNAVAILABLE"):
            return value
    return default


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    if value in (None, ""):
        return []
    return [value]


def _number(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


__all__ = ["SCHEMA_VERSION", "build_canonical_broker_readiness"]
