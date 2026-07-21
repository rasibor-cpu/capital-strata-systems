from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from backend.app.brokers.operational_state import BrokerOperationalState, operation_result

CANONICAL_BROKER_OPERATIONAL_STATUS_FIELDS = (
    "broker",
    "broker_type",
    "mode",
    "endpoint",
    "api_version",
    "server_time",
    "latency_ms",
    "rate_limit_status",
    "last_successful_sync",
    "last_failed_sync",
    "account_sync_status",
    "product_count",
    "market_data_status",
    "balance_status",
    "margin_status",
    "operational_state",
    "legacy_operational_state",
    "operation_result",
    "recommended_action",
    "expected_condition",
    "retryable",
    "failure_reason",
)


@dataclass(frozen=True)
class BrokerOperationalStatus:
    broker: str = "UNKNOWN"
    broker_type: str = "UNKNOWN"
    mode: str = "live_read_only"
    endpoint: str = "NOT_AVAILABLE"
    api_version: str = "NOT_AVAILABLE"
    server_time: str = "NOT_AVAILABLE"
    latency_ms: float | None = None
    rate_limit_status: str = "UNKNOWN"
    last_successful_sync: str = "NOT_AVAILABLE"
    last_failed_sync: str = "NOT_AVAILABLE"
    account_sync_status: str = "PENDING"
    product_count: int = 0
    market_data_status: str = "PENDING"
    balance_status: str = "NOT_AVAILABLE"
    margin_status: str = "READ_ONLY_PENDING_ACCOUNT"
    operational_state: str = BrokerOperationalState.NOT_INITIALIZED.value
    legacy_operational_state: str = "PENDING"
    operation_result: Mapping[str, Any] | None = None
    recommended_action: str = ""
    expected_condition: bool = True
    retryable: bool = False
    failure_reason: str = "NONE"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def endpoint_for_broker(broker: str, env: Mapping[str, Any] | None = None) -> str:
    name = str(broker or "").strip().upper()
    source = env if isinstance(env, Mapping) else {}
    if name == "COINBASE":
        return "https://api.coinbase.com"
    if name == "OANDA":
        value = str(source.get("OANDA_BASE_URL", "") or "").strip()
        return value or "NOT_AVAILABLE"
    return "NOT_AVAILABLE"


def build_broker_operational_status(
    payload: Mapping[str, Any] | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    source: dict[str, Any] = dict(payload) if isinstance(payload, Mapping) else {}
    source.update(overrides)

    broker = str(source.get("broker", source.get("selected_broker", "UNKNOWN")) or "UNKNOWN").upper()
    broker_type = str(source.get("broker_type", "UNKNOWN") or "UNKNOWN").upper()
    mode = str(source.get("mode", source.get("broker_mode", "live_read_only")) or "live_read_only")

    account_sync_status = _status(
        source.get("account_sync_status", source.get("account_loaded")),
        ok_label="OK",
    )
    market_data_status = _status(
        source.get("market_data_status", source.get("market_data_loaded")),
        ok_label="OK",
    )
    balance_status = _status(
        source.get("balance_status", source.get("balances_loaded")),
        ok_label="AVAILABLE",
        default_label="NOT_AVAILABLE",
    )

    if account_sync_status == "PENDING":
        margin_status = "READ_ONLY_PENDING_ACCOUNT"
    else:
        margin_status = str(source.get("margin_status", "BROKER_UNAVAILABLE") or "BROKER_UNAVAILABLE").upper()
        if margin_status == "SIMULATED":
            margin_status = "BROKER_UNAVAILABLE"

    failure_reason = _failure_reason(source)
    legacy_operational_state = str(source.get("operational_state", "") or "").upper()
    if not legacy_operational_state:
        if failure_reason not in {"NONE", "PENDING"}:
            legacy_operational_state = "DEGRADED"
        elif account_sync_status == "OK" and market_data_status == "OK":
            legacy_operational_state = "OPERATIONAL"
        else:
            legacy_operational_state = "PENDING"

    canonical_state = {
        "OPERATIONAL": BrokerOperationalState.READ_ONLY_READY,
        "READY": BrokerOperationalState.READ_ONLY_READY,
        "LIVE_READ_ONLY": BrokerOperationalState.READ_ONLY_READY,
        "DEGRADED": BrokerOperationalState.DEGRADED,
        "BLOCKED": BrokerOperationalState.EXECUTION_BLOCKED,
        "DISABLED": BrokerOperationalState.DISABLED,
        "FAILED": BrokerOperationalState.FAILED,
        "ERROR": BrokerOperationalState.FAILED,
        "UNCONFIGURED": BrokerOperationalState.CONFIGURATION_REQUIRED,
        "PENDING": BrokerOperationalState.NOT_INITIALIZED,
    }.get(legacy_operational_state, BrokerOperationalState.NOT_INITIALIZED)
    result = operation_result(
        broker=broker,
        operation="operational_status",
        state=canonical_state,
        success=canonical_state is BrokerOperationalState.READ_ONLY_READY,
        retryable=canonical_state in {BrokerOperationalState.DEGRADED, BrokerOperationalState.PROVIDER_UNAVAILABLE},
        expected_condition=canonical_state is not BrokerOperationalState.FAILED,
        failure_code=None if failure_reason in {"NONE", "PENDING"} else failure_reason,
        operator_message=(
            "Broker is ready for read-only operations"
            if canonical_state is BrokerOperationalState.READ_ONLY_READY
            else "Broker is not ready for read-only operations"
        ),
        recommended_action=(
            ""
            if canonical_state is BrokerOperationalState.READ_ONLY_READY
            else "Review broker configuration and canonical readiness"
        ),
        latency_ms=_float_or_none(source.get("latency_ms")),
    ).as_dict()

    obj = BrokerOperationalStatus(
        broker=broker,
        broker_type=broker_type,
        mode=mode,
        endpoint=str(source.get("endpoint", endpoint_for_broker(broker, source.get("env"))) or "NOT_AVAILABLE"),
        api_version=str(source.get("api_version", "v3") or "NOT_AVAILABLE"),
        server_time=str(source.get("server_time", "NOT_AVAILABLE") or "NOT_AVAILABLE"),
        latency_ms=_float_or_none(source.get("latency_ms")),
        rate_limit_status=str(source.get("rate_limit_status", "UNKNOWN") or "UNKNOWN").upper(),
        last_successful_sync=str(source.get("last_successful_sync", "NOT_AVAILABLE") or "NOT_AVAILABLE"),
        last_failed_sync=str(source.get("last_failed_sync", "NOT_AVAILABLE") or "NOT_AVAILABLE"),
        account_sync_status=account_sync_status,
        product_count=int(source.get("product_count", source.get("products_loaded", 0)) or 0),
        market_data_status=market_data_status,
        balance_status=balance_status,
        margin_status=margin_status,
        operational_state=canonical_state.value,
        legacy_operational_state=legacy_operational_state,
        operation_result=result,
        recommended_action=result["recommended_action"],
        expected_condition=result["expected_condition"],
        retryable=result["retryable"],
        failure_reason=failure_reason,
    )
    return obj.as_dict()


def _status(
    value: Any,
    *,
    ok_label: str,
    default_label: str = "PENDING",
) -> str:
    if isinstance(value, bool):
        return ok_label if value else default_label
    normalized = str(value or "").strip().upper()
    if normalized in {"OK", "READY", "PASS", "AVAILABLE", "AUTHENTICATED"}:
        return ok_label
    if normalized in {"FAILED", "FAIL", "ERROR", "UNAVAILABLE", "NOT_AVAILABLE"}:
        return "NOT_AVAILABLE"
    if normalized:
        return normalized
    return default_label


def _failure_reason(payload: Mapping[str, Any]) -> str:
    failures = payload.get("failure_reasons")
    if isinstance(failures, list) and failures:
        first = failures[0] if isinstance(failures[0], Mapping) else {}
        reason = str(first.get("reason", "") if isinstance(first, Mapping) else "").strip().upper()
        return reason or "API_ERROR"
    return "NONE"


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = [
    "CANONICAL_BROKER_OPERATIONAL_STATUS_FIELDS",
    "BrokerOperationalStatus",
    "build_broker_operational_status",
    "endpoint_for_broker",
]
